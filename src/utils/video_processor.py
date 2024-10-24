import subprocess
import json
import tempfile
from pathlib import Path

class VideoProcessor:
    def get_duration(self, video_path):
        """Get video duration in seconds"""
        result = subprocess.run([
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            video_path
        ], capture_output=True, text=True, check=True)
        
        metadata = json.loads(result.stdout)
        return float(metadata['format']['duration'])
    
    def export_with_cuts(self, input_path, output_path, markers):
        """Export video with sections removed based on markers"""
        # Create temporary file for filter script
        filter_script = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        
        # Generate filter complex command for cuts
        parts = []
        for i, (start, end) in enumerate(markers):
            parts.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]; "
                        f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]")
        
        # Concatenate all parts
        n_parts = len(markers)
        video_stream = ''.join(f'[v{i}]' for i in range(n_parts))
        audio_stream = ''.join(f'[a{i}]' for i in range(n_parts))
        filter_script.write(f"{';'.join(parts)}; "
                          f"{video_stream}concat=n={n_parts}:v=1:a=0[outv]; "
                          f"{audio_stream}concat=n={n_parts}:v=0:a=1[outa]")
        filter_script.close()
        
        # Run ffmpeg
        subprocess.run([
            'ffmpeg',
            '-i', input_path,
            '-filter_complex_script', filter_script.name,
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-y',  # Overwrite output
            output_path
        ], check=True)
        
        # Clean up
        Path(filter_script.name).unlink()

    def get_fps(self, video_path):
        """Get video frames per second"""
        result = subprocess.run([
            'ffprobe',
            '-v', 'quiet',
            '-select_streams', 'v:0',
            '-print_format', 'json',
            '-show_streams',
            video_path
        ], capture_output=True, text=True, check=True)
        
        metadata = json.loads(result.stdout)
        stream = metadata['streams'][0]
        
        # Parse frame rate fraction (e.g., "24000/1001" for 23.976 fps)
        num, den = map(int, stream['r_frame_rate'].split('/'))
        return num / den
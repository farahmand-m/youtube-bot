import datetime
import math

import youtube_dl as tube
from moviepy.editor import VideoFileClip


def identify_format(info, min_height=360, extension='mp4'):
    formats = filter(lambda item: item['ext'] == extension, info['formats'])
    formats = filter(lambda item: item['height'] >= min_height, formats)
    formats = sorted(formats, key=lambda item: item.get('tbr', math.inf))
    most_optimal, *rest = formats
    return most_optimal['format_id']


def download(url):
    options = {'outtmpl': 'videos/%(title)s.%(ext)s', 'nooverwrites': True, 'no_warnings': False, 'ignoreerrors': True}
    with tube.YoutubeDL(options) as video:
        info = video.extract_info(url, download=False)
    if info is None:  # Failed to process the page.
        return None, None, None
    duration = info['duration']
    thumbnail_url = info['thumbnail']
    options['format'] = identify_format(info)
    with tube.YoutubeDL(options) as video:
        info = video.extract_info(url, download=False)
        video_filepath = video.prepare_filename(info)
        video.download([url])
    return video_filepath, datetime.timedelta(seconds=duration), thumbnail_url


def parse_time(string):
    tokens = string.split('-')
    tokens = reversed(tokens)
    value = 0
    for i, token in enumerate(tokens):
        value += int(token) * 60 ** i
    return value


def cut_out(source, destination, start, end):
    output_filepath = f'cut/{destination}.mp4'
    video = VideoFileClip(source)
    start = max(min(start, video.duration), 0)
    end = max(min(end, video.duration), 0)
    video = video.subclip(start, end)
    video = video.without_audio()
    video.write_videofile(output_filepath)
    video.close()
    return output_filepath

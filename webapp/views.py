import os
import re

import googleapiclient.discovery
import requests
from django.http.response import HttpResponse
from django.shortcuts import render
from pytube import YouTube

from baseapp.settings import YOUTUBE_OUTPUT_DIR, YOUTUBE_API_KEY
from moviebarcode.video2moviebarcode import vid2barcode
from .forms import BarcodeForm


# Create your views here.
def home(request) -> HttpResponse:
    images = []
    video_paths = []

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = BarcodeForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process data in form.cleaned_data
            youtube_link = form.cleaned_data.get('youtube_link')

            # check if link is valid YouTube url, otherwise show 422 error
            if not is_valid_youtube_link(youtube_link):
                form = BarcodeForm()
                return render(request, 'index.html', {'form': form, 'images': images, 'video_paths': video_paths,
                                                      'message': 'Invalid link entered, please try again.'}, status=422)

            # check if link is online, otherwise show 404 error
            response = requests.head(youtube_link)
            if not response.status_code == 200:
                form = BarcodeForm()
                return render(request, 'index.html', {'form': form, 'images': images, 'video_paths': video_paths,
                                                      'message': 'Link not found, please try again.'}, status=404)

            # check if link is video or playlist, in case of playlist loop through all videos
            is_video = True if '/watch?v=' in youtube_link else False

            # download video stream to local folder, create separate folder for playlist
            if is_video:
                # download video
                image, video_path = process_video(youtube_link, YOUTUBE_OUTPUT_DIR)
                images.append(image)
                video_paths.append(video_path)
            else:
                # extract playlist from YouTube link
                playlist_id = youtube_link.split('/playlist?list=')[1]
                playlist_items = get_video_from_playlist(playlist_id)

                # download playlist videos in its own directory
                playlist_dir = YOUTUBE_OUTPUT_DIR / playlist_id
                if not os.path.exists(playlist_dir):
                    os.makedirs(playlist_dir, exist_ok=True)

                # loop through all videos of playlist
                for playlist_item in playlist_items:
                    youtube_link = 'https://www.youtube.com/watch?v=' + playlist_item['snippet']['resourceId'][
                        'videoId']
                    image, video_path = process_video(youtube_link, playlist_dir)
                    images.append(image)
                    video_paths.append(video_path)

    # if a GET (or any other method) we'll create a blank form
    form = BarcodeForm()

    return render(request, 'index.html', {'form': form, 'images': images, 'video_paths': video_paths, 'message': None})


def is_valid_youtube_link(link) -> bool:
    p = re.compile(r'(https?:\/\/)?(www\.)?youtube\.com\/(watch\?v=[0-9a-zA-Z-]{11}|playlist\?list=[0-9a-zA-Z-]{34})')
    x = p.match(link)

    return True if x and x.group(1) else False


def download_video(url, path) -> str:
    return YouTube(url).streams.filter(progressive=True, file_extension='mp4').get_highest_resolution().download(path)


def get_video_from_playlist(playlist_id) -> list:
    youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.playlistItems().list(part='snippet', playlistId=playlist_id, maxResults=50)
    response = request.execute()

    playlist_items = []
    while request is not None:
        response = request.execute()
        playlist_items += response["items"]
        request = youtube.playlistItems().list_next(request, response)

    return playlist_items


def get_video_from_channel(channel_id) -> list:
    youtube = googleapiclient.discovery.build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.playlists().list(part='snippet', channelId=channel_id, maxResults=50)
    response = request.execute()

    playlists = []
    while request is not None:
        response = request.execute()
        playlists += response["items"]
        request = youtube.playlists().list_next(request, response)

    return playlists


def process_video(youtube_link, path) -> tuple:
    video_path = download_video(youtube_link, path)

    # create image
    image = 'output/' + video_path.split('\\')[-1].split('.')[0] + '.png'

    # pass local video path to generate barcode
    vid2barcode(video_path=video_path)

    return image, video_path

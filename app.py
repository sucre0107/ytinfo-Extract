import logging
import os
from flask import Flask, request, jsonify, send_from_directory
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google_auth_httplib2 import AuthorizedHttp
import httplib2
from googleapiclient.errors import HttpError


# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, static_folder='static')

# 使用绝对路径或相对路径处理服务账户文件
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'apis-385516-79af24303670.json')
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
http = AuthorizedHttp(credentials, http=httplib2.Http(disable_ssl_certificate_validation=True))
youtube = build('youtube', 'v3', http=http)

# 你的其他路由和功能代码

def fetch_comments(video_id):
    logging.info(f'Fetching comments for video_id: {video_id}')
    comments_data = []
    next_page_token = None

    while True:
        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            pageToken=next_page_token
        )
        response = request.execute()
        logging.info(f'Received response for comments: {response}')

        for item in response.get("items", []):
            comment_snippet = item["snippet"]["topLevelComment"]["snippet"]
            comment_data = {
                "username": comment_snippet.get("authorDisplayName", "Unknown"),
                "comment": comment_snippet.get("textOriginal", ""),
                "published_at": comment_snippet.get("publishedAt", ""),
                "replies": []
            }

            if item["snippet"]["totalReplyCount"] > 0:
                reply_request = youtube.comments().list(
                    part="snippet",
                    parentId=item["id"],
                    maxResults=100
                )
                reply_response = reply_request.execute()
                logging.info(f'Received response for replies: {reply_response}')

                for reply_item in reply_response.get("items", []):
                    reply_snippet = reply_item["snippet"]
                    reply_data = {
                        "username": reply_snippet.get("authorDisplayName", "Unknown"),
                        "comment": reply_snippet.get("textOriginal", ""),
                        "published_at": reply_snippet.get("publishedAt", "")
                    }
                    comment_data["replies"].append(reply_data)

            comments_data.append(comment_data)

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return comments_data

def get_video_title(video_id):
    logging.info(f'Fetching title for video_id: {video_id}')
    request = youtube.videos().list(
        part="snippet",
        id=video_id
    )
    response = request.execute()
    logging.info(f'Received response for title: {response}')
    return response["items"][0]["snippet"]["title"]

def get_video_description(video_id):
    logging.info(f'Fetching description for video_id: {video_id}')
    request = youtube.videos().list(
        part="snippet",
        id=video_id
    )
    response = request.execute()
    logging.info(f'Received response for description: {response}')
    return response["items"][0]["snippet"]["description"]

def get_video_captions(video_id):
    logging.info(f'Fetching captions for video_id: {video_id}')
    captions_request = youtube.captions().list(
        part="snippet",
        videoId=video_id
    )
    captions_response = captions_request.execute()
    logging.info(f'Received response for captions: {captions_response}')

    caption_id = None
    for item in captions_response.get("items", []):
        if item["snippet"]["language"] == "en":
            caption_id = item["id"]
            break

    if not caption_id:
        logging.warning(f'No captions available for video_id: {video_id}')
        return "No captions available"

    captions_response = youtube.captions().download(
        id=caption_id,
        tfmt='srt'
    ).execute()
    logging.info(f'Received captions content for video_id: {video_id}')
    return captions_response.decode('utf-8')

@app.route('/')
def serve_frontend():
    logging.info('Serving frontend')
    return send_from_directory(app.static_folder, 'index.html')

from google.auth.transport import requests
from google.oauth2 import id_token
@app.route('/verify_token', methods=['POST'])
def verify_token():
    token = request.json.get('id_token')
    try:
        # 验证ID令牌
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), '650241351969-eqll2jmrvhs0p1eqqmen5kh06gs7f66r.apps.googleusercontent.com')

        # 如果令牌是合法的，返回用户的Google账户信息
        if 'sub' in idinfo:
            return jsonify({"success": True, "user": idinfo['email']})
        else:
            return jsonify({"success": False}), 401
    except ValueError as e:
        # 处理无效的令牌
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/get_comments', methods=['GET'])
def get_comments():
    video_id = request.args.get('video_id')
    logging.info(f'GET /get_comments with video_id: {video_id}')
    if not video_id:
        logging.error('No video ID provided')
        return jsonify({"error": "Please provide a video ID"}), 400

    comments = fetch_comments(video_id)
    return jsonify(comments)

@app.route('/get_video_title', methods=['GET'])
def get_video_title_route():
    video_id = request.args.get('video_id')
    logging.info(f'GET /get_video_title with video_id: {video_id}')
    if not video_id:
        logging.error('No video ID provided')
        return jsonify({"error": "Please provide a video ID"}), 400

    title = get_video_title(video_id)
    return jsonify({"title": title})


@app.route('/get_description', methods=['GET'])
def get_video_description_route():
    video_id = request.args.get('video_id')
    logging.info(f'GET /get_video_description with video_id: {video_id}')

    if not video_id:
        logging.error('No video ID provided')
        return jsonify({"error": "Please provide a video ID"}), 400

    try:
        description = get_video_description(video_id)
        if description:
            logging.info(f'Successfully fetched description for video_id: {video_id}')
            return jsonify({"description": description})
        else:
            logging.warning(f'No description found for video_id: {video_id}')
            return jsonify({"error": "No description found"}), 404
    except Exception as e:
        logging.error(f'Error fetching description for video_id: {video_id}, Error: {e}')
        return jsonify({"error": "Failed to fetch description"}), 500

@app.route('/get_captions', methods=['GET'])
def get_video_captions_route():
    video_id = request.args.get('video_id')
    logging.info(f'GET /get_video_captions with video_id: {video_id}')
    if not video_id:
        logging.error('No video ID provided')
        return jsonify({"error": "Please provide a video ID"}), 400

    try:
        captions = get_video_captions(video_id)  # 确保传递了 video_id 参数
        return jsonify({"captions": captions})
    except Exception as e:
        logging.error(f'Error fetching captions for video_id: {video_id}, Error: {e}')
        return jsonify({"error": "Failed to fetch captions"}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port='5555')
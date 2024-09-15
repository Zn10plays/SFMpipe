import os
import subprocess
import requests
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
from util.upload import upload_to_edgestore

# Load environment variables from the .env file
load_dotenv()

# MongoDB client connection
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client[os.getenv("MONGO_DB")]
collection = db["listings"]

# Function to download video
def download_video(video_url, output_path):
    print(f"Downloading video from {video_url}...")
    response = requests.get(video_url, stream=True)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print("Video downloaded successfully.")
    else:
        raise Exception(f"Failed to download video: {response.status_code}")

# Function to process video and generate point cloud using COLMAP
def generate_point_cloud(video_path, output_dir):
    print("Running COLMAP to generate point cloud...")
    try:
        # Run COLMAP commands to create a point cloud from the video frames
        # 1. Extract frames from video
        subprocess.run(['colmap', 'video', 'extract', '--video_path', video_path, '--output_path', output_dir], check=True)
        
        # 2. Run feature extraction
        subprocess.run(['colmap', 'feature_extractor', '--database_path', os.path.join(output_dir, 'database.db'), '--image_path', output_dir], check=True)
        
        # 3. Run exhaustive matcher
        subprocess.run(['colmap', 'exhaustive_matcher', '--database_path', os.path.join(output_dir, 'database.db')], check=True)
        
        # 4. Create sparse reconstruction (structure from motion)
        sparse_model_dir = os.path.join(output_dir, 'sparse')
        os.makedirs(sparse_model_dir, exist_ok=True)
        subprocess.run(['colmap', 'mapper', '--database_path', os.path.join(output_dir, 'database.db'), '--image_path', output_dir, '--output_path', sparse_model_dir], check=True)
        
        print("Point cloud generated successfully.")
        return sparse_model_dir
    except subprocess.CalledProcessError as e:
        raise Exception(f"COLMAP processing failed: {e}")

def process_new_listing(change):
    try:
        if change['operationType'] == 'insert':
            new_listing = change['fullDocument']
            video_url = new_listing['vedioSrc']
            listing_id = new_listing['_id']

            # local refrence        
            video_path = f"/tmp/{listing_id}.mp4"
            output_dir = f"/tmp/{listing_id}_output"
            
            # Download the video
            download_video(video_url, video_path)
            
            # Process the video using COLMAP to generate the point cloud
            point_cloud_dir = generate_point_cloud(video_path, output_dir)
            
            # Upload the generated point cloud to EdgeStore
            point_cloud_url = upload_to_edgestore(point_cloud_dir)
            
            # Update the MongoDB document with the new point cloud URL
            collection.update_one({'_id': listing_id}, {'$set': {'pointCloudSrc': point_cloud_url}})
            print(f"Updated listing {listing_id} with point cloud URL: {point_cloud_url}")
            
    except Exception as e:
        print(f"Error processing listing: {e}")

def main():
    try:
        print("Listening for changes in the 'listings' collection...")
        with collection.watch() as stream:
            for change in stream:
                process_new_listing(change)
    except ConnectionFailure as e:
        print(f"MongoDB connection failed: {e}")

if __name__ == "__main__":
    main()

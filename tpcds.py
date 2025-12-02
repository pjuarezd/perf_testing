# Moved the main.py functionality from tpcds-kit to the root directory and renamed it to "tpcds".
# Updated the script to work from the root directory while maintaining the same flags and functionality.

import argparse
import os
import subprocess
import shutil
import glob
from dotenv import load_dotenv

# Adjust paths to work from the root directory
TPCDS_KIT_DIR = os.path.join(os.path.dirname(__file__), "tpcds-kit")
RAW_FILES_DIR = os.path.join(TPCDS_KIT_DIR, "test_data/raw_files")
PARQUET_DIR = os.path.join(TPCDS_KIT_DIR, "test_data/parquet")

# Load environment variables
load_dotenv()

def generate_data(scale_factor, non_interactive=False):
    print(f"You are about to generate approximately {scale_factor}GB of data.")
    if not non_interactive:
        confirmation = input("Do you want to proceed? (y/n): ").strip().lower()
        if confirmation != "y":
            print("Operation cancelled.")
            return
    subprocess.run(["python", os.path.join(TPCDS_KIT_DIR, "data_generator.py"), "--scale-factor", str(scale_factor)])

def upload_data(test_mode, use_spark, custom_tmp_dir=""):
    # Retrieve S3 configuration from environment variables
    s3_bucket = os.environ.get("S3_BUCKET_NAME")
    s3_endpoint = os.environ.get("S3_ENDPOINT_URL")

    if not s3_bucket or not s3_endpoint:
        print("Error: S3 configuration is missing in the .env file.")
        return

    # Check if raw files exist
    if not os.path.exists(RAW_FILES_DIR) or not any(f.endswith(".dat") for f in os.listdir(RAW_FILES_DIR)):
        print("No .dat files found in 'test_data/raw_files'. Nothing to convert or upload.")
        return

    if test_mode:
        print("TEST MODE: Listing source and target paths")
        if os.path.exists(RAW_FILES_DIR):
            for file in os.listdir(RAW_FILES_DIR):
                if file.endswith(".dat"):
                    parquet_file = os.path.splitext(file)[0] + ".parquet"
                    print(f"Source: {os.path.join(PARQUET_DIR, parquet_file)} Target: s3://{s3_bucket}/{os.path.splitext(file)[0]}/{parquet_file}")
        return

    # Run the appropriate script to convert .dat to .parquet
    if use_spark:
        commandArguments = [ "python", os.path.join(TPCDS_KIT_DIR, "parquet_transform_spark.py") ]
        if custom_tmp_dir != "":
            commandArguments.append("--custom_dir")
            commandArguments.append(custom_tmp_dir)
        subprocess.run(commandArguments)
    else:
        subprocess.run(["python", os.path.join(TPCDS_KIT_DIR, "data_to_parquet.py")])

    # Check if parquet files exist
    if not os.path.exists(PARQUET_DIR) or not glob.glob(f'{PARQUET_DIR}/**/*.parquet', recursive=True):
        print("No .parquet files found in 'test_data/parquet'. Nothing to upload.")
        return

    # Run the upload_parquet.py script
    command = ["python", os.path.join(TPCDS_KIT_DIR, "upload_parquet.py"), "--directory", PARQUET_DIR]
    subprocess.run(command)

def cleanup(non_interactive=False):
    if not non_interactive:
        print("WARNING: This will delete all .dat files in 'test_data/raw_files' and all .parquet files in 'test_data/parquet'.")
        confirmation = input("Do you want to proceed? (y/n): ").strip().lower()
        if confirmation != "y":
            print("Operation cancelled.")
            return

    # Delete .dat files
    if os.path.exists(RAW_FILES_DIR):
        for file in os.listdir(RAW_FILES_DIR):
            if file.endswith(".dat"):
                os.remove(os.path.join(RAW_FILES_DIR, file))
        print("Deleted all .dat files in 'test_data/raw_files'.")

    # Delete .parquet files
    if os.path.exists(PARQUET_DIR):
        for file in os.listdir(PARQUET_DIR):
            if file.endswith(".parquet"):
                os.remove(os.path.join(PARQUET_DIR, file))
        print("Deleted all .parquet files in 'test_data/parquet'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TPC-DS Test Kit: Manage data generation, conversion, upload, and cleanup.")
    parser.add_argument("--yes", action="store_true", help="Non-interactive mode, assume yes to prompts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subparser for data generation
    generate_parser = subparsers.add_parser("generate", help="Generate TPC-DS data")
    generate_parser.add_argument("--scale", type=int, required=True, help="Scale factor for data generation (e.g., 1 for 1GB, 10 for 10GB).")

    # Subparser for upload
    upload_parser = subparsers.add_parser("upload", help="Convert and upload Parquet files to S3")
    upload_parser.add_argument("--test", action="store_true", help="Run in test mode to output source and target paths without uploading")
    upload_parser.add_argument("--spark", action="store_true", help="Use Spark-based Parquet transformation")
    upload_parser.add_argument("--custom_dir", type=str, help="Use as temporary directory instead of /tmp", default="")

    # Subparser for cleanup
    cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup .dat and .parquet files")

    args = parser.parse_args()

    if args.command == "generate":
        generate_data(args.scale, args.yes)
    elif args.command == "upload":
        upload_data(args.test, args.spark, args.custom_dir)
    elif args.command == "cleanup":
        cleanup(args.yes)
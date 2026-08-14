#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$ROOT/build"

rm -rf "$BUILD/lambda" "$BUILD/lambda.zip"
mkdir -p "$BUILD/lambda"

uv export \
    --project "$ROOT" \
    --frozen \
    --no-dev \
    --no-emit-project \
    --no-hashes \
    --format requirements.txt \
    --output-file "$BUILD/requirements.txt"

python3 -m pip install \
    --requirement "$BUILD/requirements.txt" \
    --target "$BUILD/lambda" \
    --platform manylinux2014_x86_64 \
    --implementation cp \
    --python-version 3.12 \
    --abi cp312 \
    --only-binary=:all:

cp -R "$ROOT/src" "$BUILD/lambda/src"

mkdir -p "$BUILD/lambda/data"
cp -R "$ROOT/data/reference" "$BUILD/lambda/data/reference"

(
    cd "$BUILD/lambda"
    zip -qr "$BUILD/lambda.zip" .
)

echo "Created $BUILD/lambda.zip"

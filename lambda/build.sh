#!/usr/bin/env bash
set -e

build_lambda () {
  NAME=$1
  HANDLER=$2

  rm -rf build/$NAME
  mkdir -p build/$NAME

  cp handlers/$HANDLER.py build/$NAME/$HANDLER.py
  cp -r shared build/$NAME/shared

  (cd build/$NAME && zip -r ../$NAME.zip .)
}

build_lambda add-to-cart add
build_lambda get-cart get
build_lambda update-cart update
build_lambda remove-cart remove


# chmod +x build.sh
# ./build.sh
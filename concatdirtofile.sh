#!/bin/sh
rm -f output.txt

# Use "$@" to pass all script arguments to the find command
find "$@" -type f -name '*.py' | while read -r file; do
    echo "File: $file" >> output.txt
    cat "$file" >> output.txt
    echo "\n" >> output.txt
done

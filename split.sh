#!/bin/sh
i=1
cat "$1" | while read l; do
    printf -v fname "%03d" "$i"
    printf "%s\n" "$l" > "$2"/"$fname".jpl
    i=$((i + 1))
done

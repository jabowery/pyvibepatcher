#!/bin/bash
concatdirtofile.sh `ls -1|egrep -v '__pycache__|fixes|output.txt|newconcat'`

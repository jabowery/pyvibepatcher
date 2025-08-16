#!/bin/sh
rm output.txt
find $1 -type f -name '*.py'| while read -r file; do                                                                       
   echo "File: $file" >> output.txt                                                                            
   cat "$file" >> output.txt                                                                                   
   echo "\n" >> output.txt                                                                                  
done

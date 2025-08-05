#!/bin/sh
find $1 -type f -name '*.py'| while read -r file; do                                                                       
   echo "File: $file" >> output.txt                                                                            
   cat "$file" >> output.txt                                                                                   
   echo -e "\n" >> output.txt                                                                                  
done

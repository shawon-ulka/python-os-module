import os
import shutil
source="C:\\Users\\S-AUT001\\Desktop\\source"
dest="C:\\Users\\S-AUT001\\Desktop\\root"

for r,d,f in os.walk(source):
    for file in f:
        src_file_path=os.path.join(r,file)
        src_file=file

for r,d,f in os.walk(dest):
    for file in f:
        if file==src_file:
            shutil.copy(src_file_path,r)

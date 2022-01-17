import os
root="C:\\Users\\S-AUT001\\Desktop\\root"
files=[]
fileWithPath=[]
for path,d,f in os.walk(root):
    for file in f:
        fileWithPath.append(os.path.join(path,file))
        files.append(file)

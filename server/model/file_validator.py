import fleep
from os import listdir
from os.path import isfile, join
import mimetypes
import pathlib

from exceptions import ValidationException

def validate_documents(scanner, scan_file_mount, stage_dir, filename_mime_dict):
    for file in listdir(stage_dir):
        full_path = join(stage_dir, file)
        if isfile(full_path):
            if mimetypes.guess_type(full_path)[0].startswith('text'):
                # Skip for text file. TODO The way we detect it here is not great. Improve text file detection
                continue
            # For binary files, use magic to detect file types
            with open(full_path, 'rb') as stream:
                ext = pathlib.Path(full_path).suffix
                content = stream.read(128)
                info = fleep.get(content)
                if not info.extension_matches(ext[1:]):
                     raise ValidationException("Magic mismatch for extension in file: {}. Expected: {}, found:{}".format(file, ext, info.extension))
                if not info.mime_matches(filename_mime_dict[full_path]):
                     raise ValidationException("Magic mismatch for mimeType in file: {}. Expected: {}, found:{}".format(file, ext, info.extension))
                # print('Type:', info.type)
                # print('File extension:', info.extension[0])
                # print('MIME type:', info.mime[0]) 

    # TODO this code is temporary
    # command="""
    #    docker run -it --rm --name clamdscan --network dl --mount type=bind,source={},target=/scandir --mount type=bind,source=$DOCRIVER_GW_HOME/src/test/conf/# clam.remote.conf,target=/conf/clam.remote.conf  clamav/clamav:stable_base clamdscan --fdpass --verbose --stdout -c /conf/clam.remote.conf /scandir
    # """.format(stage_dir)
    # result = subprocess.run(command, shell=True, stderr=STDOUT, stdout=PIPE, text=True, check=True)
    # print(result.stdout)
    # logging.getLogger().info("Scan result: ", result.stdout)
    # os.system(command) 

    # This assumes that the staging area is created just below the untrusted filesystem mount
    result = scanner.scan(join(scan_file_mount, pathlib.Path(stage_dir).name))
    for kv in result.items():
        if kv[1][0] != 'OK':
            raise ValidationException("Virus check failed on file: {}. Error: {}".format(pathlib.Path(kv[0]).name, kv[1]))
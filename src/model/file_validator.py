import fleep
from os import listdir
from os.path import isfile, join
import pathlib
import logging

from exceptions import ValidationException

def validate_documents(principal, scanner, scan_file_mount, stage_dir, filename_mime_dict):
    for file in listdir(stage_dir):
        full_path = join(stage_dir, file)
        if isfile(full_path):
            if filename_mime_dict[full_path].startswith('text'):
                # Skip for text file. TODO The way we detect it here is not great. Improve text file detection
                continue
            # For binary files, use magic to detect file types
            with open(full_path, 'rb') as stream:
                ext = pathlib.Path(full_path).suffix
                content = stream.read(128)
                info = fleep.get(content)
                if not info.extension_matches(ext[1:]):
                    logging.getLogger("Integrity").warning("Extension mismatch in file: {}. Expected: {}, found:{}, principal: {}".format(file, ext, info.extension, principal))
                    raise ValidationException("Extension mismatch in file: {}. Expected: {}, found:{}".format(file, ext, info.extension))
                if not info.mime_matches(filename_mime_dict[full_path]):
                     logging.getLogger("Integrity").warning("Magic mismatch in file: {}. Expected: {}, found:{}, principal: {}".format(file, filename_mime_dict[full_path], info.mime, principal))
                     raise ValidationException("Magic mismatch in file: {}. Expected: {}, found:{}".format(file, filename_mime_dict[full_path], info.mime))
                # print('Type:', info.type)
                # print('File extension:', info.extension[0])
                # print('MIME type:', info.mime[0]) 

    # This assumes that the staging area is created just below the untrusted filesystem mount
    result = scanner.scan(join(scan_file_mount, pathlib.Path(stage_dir).name))
    for kv in result.items():
        if kv[1][0] != 'OK':
            logging.getLogger("Integrity").warning("Integrity check failed on file {}. Error: {}, principal: {}".format(kv[0], kv[1], principal))
            raise ValidationException("Virus check failed on file: {}. Error: {}".format(kv[0], kv[1]))
        
    # TODO this code is temporary
    # command="""
    #    docker run -it --rm --name clamdscan --network dl --mount type=bind,source={},target=/scandir --mount type=bind,source=$DOCRIVER_GW_HOME/src/test/conf/# clam.remote.conf,target=/conf/clam.remote.conf  clamav/clamav:stable_base clamdscan --fdpass --verbose --stdout -c /conf/clam.remote.conf /scandir
    # """.format(stage_dir)
    # result = subprocess.run(command, shell=True, stderr=STDOUT, stdout=PIPE, text=True, check=True)
    # print(result.stdout)
    # logging.getLogger().info("Scan result: ", result.stdout)
    # os.system(command) 
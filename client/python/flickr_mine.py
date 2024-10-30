#!/usr/bin/env python

import argparse
import flickrapi
import urllib
import sys
import os
import shutil
import logging
import requests
import json
from PIL import Image
from datetime import datetime

from docriver_auth.keystore import get_entries
from docriver_auth.auth_token import issue

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", help="Flickr API key")
    parser.add_argument("--secret", help="Flickr API secret")
    parser.add_argument("--photoset", help="Photo set (album)")
    parser.add_argument("--tags", nargs='+', help="Tags to search for")
    parser.add_argument("--max", type=int, help="Maximum photos to download", default=100)
    parser.add_argument("--size", help="Size of the photo to download. Valid options are: c/m/n/o/q/s/t. See https://librdf.org/flickcurl/api/flickcurl-searching-search-extras.html for details", default='sq')
    parser.add_argument("--filterByRatioValue", type=float, help="Filter images based on width to height ratio", default=1.33)
    parser.add_argument("--filterByRatioTolerance", type=float, help="Tolerance band for filtered images based on ratio", default=0.5)

    parser.add_argument("--rawFilesystemMount", help="mount point of the shared filesystem where raw documents is stored by applications. The applications can copy files to this location and specify the location instead of uploading")

    parser.add_argument("--docriverUrl", help="Document gateway URL", default='http://localhost:5000')
    parser.add_argument("--prefix", help="Document name prefix", default='')

    parser.add_argument('--keystore', default=os.path.join(os.getenv('HOME'), '.ssh/docriver.p12'),
                        help='A PKCS12 keystore file')
    parser.add_argument('--keystorePassword', default=None,
                        help='Keystore password')
    parser.add_argument('--subject', default='anon',
                        help='Principal of the subject')
    parser.add_argument('--audience', default='docriver',
                        help='Target application')
    parser.add_argument('--resource', default='document',
                        help='resource to authorize')
    
    parser.add_argument("--realm", help="Realm to submit document to")

    parser.add_argument('--noverify', action='store_true')

    parser.add_argument("--log", help="log level (valid values are DEBUG, INFO, WARN, ERROR, NONE", default='WARN')

    
    args = parser.parse_args()
    
    if not args.api:
        raise Exception('Flickr API key is mandatory')
    
    if not args.secret:
        raise Exception('Flickr API secret is mandatory')

    if not args.realm:
        raise Exception('Realm is mandatory')
    return args

def pretty_print(req):
    print('{}\n{}\n{}\n\n{}'.format(
        '-----------START-----------',
        req.method + ' ' + req.url,
        '\r\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
        req.body,
    ))

if __name__ == '__main__':
    args = parse_args()
    logging.basicConfig(level=args.log)

    # If we are using a raw file ingestion, the location needs to be shared between the client and the server
    tmp_folder = None
    path_prefix=''
    if args.rawFilesystemMount:
        tmp_folder = os.path.join(args.rawFilesystemMount, args.realm)
        path_prefix = '/'
    else:
        tmp_folder = os.path.join('/tmp/docriver', args.realm)
        
    if os.path.isdir(tmp_folder):
        shutil.rmtree(tmp_folder)
    os.makedirs(tmp_folder)

    flickr = flickrapi.FlickrAPI(args.api, args.secret, cache=True)    
    extras_list=['tags','geo']
    size_extra = 'url_' + args.size
    extras_list.append(size_extra)
    extras = ','.join(extras_list)

    tags = ','.join(args.tags) if args.tags else ''

    photos = None
    if args.photoset:
        if tags:
            logging.getLogger().warning('Search by tags not supported when a photoset is specified')
        photos = flickr.walk_set(args.photoset, extras=extras)
    else:
        photos = flickr.walk(tag_mode='all', tags=tags, extras=extras)

    cur_time = datetime.now().strftime("%Y%m%d%H%M%S")
    manifest = {
        'tx': cur_time,
        'documents': []
    }

    count = 0
    file_map = []
    #requests.urllib3.disable_warnings()
    for photo in photos:
        url = photo.get(size_extra)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.getLogger().debug("Image: {0}, title: {1}, tags: {2},  geo: {3}, url: {4}".format(count+1, photo.get('title'), photo.get('tags'), photo.get('geo'), url))
        if url is None:
            continue
        filename = url[url.rfind('/')+1:]        
        full_path = os.path.join(tmp_folder, filename)
        urllib.request.urlretrieve(url, full_path)
        if args.filterByRatioValue:
            image = Image.open(full_path)
            dimension = image.size
            ratio = dimension[0]/dimension[1]
            if abs(ratio - args.filterByRatioValue) > args.filterByRatioTolerance:
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    logging.getLogger().debug("Image: {} did not meet ratio filter. Skipping".format(filename))
                os.remove(full_path)
                continue
        
        if not args.rawFilesystemMount:
            pair = ('files', open(full_path, 'rb'))
            file_map.append(pair)

        doc_attribs = {
            'document': args.prefix + ('/' if args.prefix else '') + cur_time + '/' + filename,
            'type': 'image',
            "content": {
                "path": path_prefix + filename
            }
        }

        manifest['documents'].append(doc_attribs)
        count = count + 1
        if count >= args.max:
            break

    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(args.keystore, args.keystorePassword)
    encoded, payload = issue(private_key, signer_cn, args.subject, args.audience, 60,  args.resource, {'txType': 'submit', 'documentCount': count})
    manifest['authorization'] = 'Bearer ' + encoded

    url = args.docriverUrl + '/tx/' + args.realm
    response = None
    if args.rawFilesystemMount:
        headers =  {"Content-Type":"application/json", "Accept": "application/json"}
        response = requests.post(url, json=manifest, headers=headers, verify=not args.noverify)
    else:
        # HTTP multipart form
        json_object = json.dumps(manifest, indent=4)
        with open("/tmp/manifest.json", "w") as outfile:
            outfile.write(json_object)
        pair = ('files', open("/tmp/manifest.json", 'r'))
        file_map.append(pair)

        headers =  {"Accept": "application/json"}
        # req = requests.Request('POST',args.docriverUrl + '/tx',headers=headers,files=file_map)
        # prepared = req.prepare()
        # pretty_print(prepared)
        # s = requests.Session()
        # s.send(prepared)
        response = requests.post(url, files=file_map, headers=headers, verify=not args.noverify)

    if response.status_code != 200:
        print("Status: {}, message: {}".format(response.status_code, response.text))
        exit(1)
    else:
        print(response.text)


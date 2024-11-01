
def parse_url(location):
    assert location.startswith('s3://')
    bucket_path = location[len('s3://'):]
    index = bucket_path.find('/')
    assert index > 0
    bucket = bucket_path[0:index]
    path = bucket_path[index+1:]
    return bucket,path
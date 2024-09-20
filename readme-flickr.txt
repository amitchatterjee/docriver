# Append the following options when using HTTPS and self-signed certificate
--docriverUrl https://localhost:8443 --noverify

# Run with shared raw filesystem mount
flickr_mine.py --api $FLICKR_API_KEY --secret $FLICKR_API_SECRET --realm p123456 --tags cheetah --max 10 --prefix cheetah --rawFilesystemMount "$HOME/storage/docriver/raw"  --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io

# Run with HTTP multipart
flickr_mine.py --api $FLICKR_API_KEY --secret $FLICKR_API_SECRET --realm p123456 --tags cheetah --max 10 --prefix cheetah --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io

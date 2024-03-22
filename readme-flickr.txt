# Run with shared raw filesystem mount
python $DOCRIVER_GW_HOME/src/flickr_mine.py --api $FLICKR_API_KEY --secret $FLICKR_API_SECRET --realm p123456 --tags cheetah --max 10 --prefix cheetah --rawFilesystemMount "$HOME/storage/docriver/raw"  --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io

# Run with HTTP multipart
python $DOCRIVER_GW_HOME/src/flickr_mine.py --api $FLICKR_API_KEY --secret $FLICKR_API_SECRET --realm p123456 --tags cheetah --max 10 --prefix cheetah --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io
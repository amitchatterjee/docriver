## Introduction
This docriver-gateway repository is part of the Docriver project. 

Docriver is an initiative to create a highly-scalable document ingestion and processing system for use by large enterprises and service providers. Documents include various forms of text files (XML, plaintext, etc), and binary fies (images, videos, audio, pdf, msword, xls, etc.). As we are increasing are use of documents for building solutions, we need services to ingest documents safely and securely from "untrusted" sources on the Internet and run them through processing pipelines to extract the information we need for our applications.

This repository deals with the gateway aspect of the system. The function of the gateway is to receive documents from extrnal and internal entities, sanitize them and store them from downstream processing. The components include:

- Endpoints to receive documents
- An object storage for storing documents
- An database for storing document metadata
- A virus scanner software for validating the documents
- Filesystem volumes to store files during the ingestion process
- The gateway application that handles document ingestion requests.

![Component architecture!](doc/docriver-gateway.drawio.png "Gateway Components")
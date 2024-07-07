from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

def get_entries(keystore, password):
    out = None
    with open(keystore, 'rb')as stream:
        data = stream.read()
        password= bytes(password, 'utf-8')
        out = pkcs12.load_key_and_certificates(data, password)
    private_key = out[0]
    public_key = private_key.public_key()
    signer_cert = out[1]
    signer_cn = signer_cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value

    public_keys = {}
    for i in range(2, len(out)):
        l = out[i]
        for cert in l:
            cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            public_keys[cn] = cert.public_key()

    return private_key, public_key, signer_cert, signer_cn, public_keys
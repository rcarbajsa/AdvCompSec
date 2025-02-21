import Crypto
from Crypto.PublicKey import RSA
from Crypto import Random
import ast
class ObjSRSA:
    def generate_key(length, keyFile):
        random_generator = Random.new().read
        privateKey = RSA.generate(length, random_generator) #generate pub and priv key
        publicKey = privateKey.publickey() # pub key export for exchange
        with open(keyFile,'wb') as f:
            f.write(privateKey.export_key('PEM'))
            f.write(b'  ')
            f.write(publicKey)
        return (publicKey, privateKey)

    def encrypt(data, key):
        encrypted = key.encrypt(message, 32)
        print('encrypted message:' + str(encrypted)) #ciphertext
        return encrypted

    def decrypt(data, key):
        decrypted = key.decrypt(ast.literal_eval(str(encrypted)))
        print('decrypted' + str(decrypted))
    def importServerKey():
        with open('public.pem','rb') as f:
            return RSA.importKey(f.read())
    def getKeys(keyFile):
        privKey, pubKey = None
        with open(privKeyFile, 'rb') as f:
            result = f.read()
            keys = result.split(b'  ')
            privKey = RSA.importKey(keys[0])
            pubKey = RSA.importKey(keys[1])
        return (privKey, pubKey)
        
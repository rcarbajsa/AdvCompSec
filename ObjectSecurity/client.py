import socket
from messageDecoder import *
from enum import IntEnum
from rsa import ObjSRSA as RSA
from diffie_hellman import ObjSDH as DH 
from aes import ObjSAES as AES
from Crypto.Hash import SHA256
from getopt import getopt

# TODO finish helper functions
# TODO figure out actual max length of packets for receiving
# TODO resends

class ClientState(IntEnum):
    UNINITIALZED = 0
    HANDSHAKE_STARTED = 1
    CONNECT_RESPONSE_RECEIVED = 2
    DIFFIE_HELLMAN_SENT = 3
    KEYS_ADVERTISED = 4
    DATA_EXCHANGE = 5
    SHUTDOWN_SENT = 6
    SHUTDOWN_COMPLETE = 7

class DataExchangeState(IntEnum):
    UNINITIALIZED = 0
    REQUEST_SENT = 1
    OBJECT_REQUEST_ACK_RECEIVED = 2
    EXCHANGE_COMPLETE = 3

class ServerData:
    def __init__(self, host=None, port=None, sock=None, pubKey=None, sessionKey=None, objectKeyHashes=[], connectionState=ClientState.UNINITIALZED):
        self.host = host
        self.port = port
        self.pubKey = pubKey
        self.sessionKey = sessionKey
        self.objectKeyHashes = objectKeyHashes
        self.connectionState = connectionState
        self.sock = sock
        self.requestNumbers = {}
        
    def getHost(self):
        return self.host
    def setHost(self, host):
        self.host = host
    
    def getPort(self):
        return self.port
    def setPort(self, port):
        self.port = port
        
    def getSocket(self):
        return self.sock
    def setSocket(self, sock):
        self.sock = sock
        
    def getPubKey(self):
        return self.pubKey
    def setPubKey(self, pubKey):
        self.pubKey = pubKey
        
    def getSessionKey(self):
        return self.sessionKey
    def setSessionKey(self, sessionKey):
        self.sessionKey = sessionKey
        
    def getObjectKeyHashes(self):
        return self.objectKeyHashes
    def setObjectKeyHashes(self, objectKeyHashes):
        self.objectKeyHashes = objectKeyHashes
    
    def getConnectionState(self):
        return self.connectionState
    def setConnectionState(self, connectionState):
        self.connectionState = connectionState
    
    def getRequestNumberState(self, requestNumber):
        return self.requestNumbers.get(requestNumber)
    def checkRequestNumberUsed(self, requestNumber):
        return self.requestNumbers.get(requestNumber) != None
    def setRequestNumberState(self, requestNumber, state):
        self.requestNumbers[requestNumber] = state
    
    def getRequestNumberData(self):
        return self.requestData
    def setRequestNumberData(self, requestNumber, data):
        self.requestData[requestNumber] = data
    def clearRequestNumberData(self, requestNumber):
        self.pop(requestNumber)


def runClient(serverKeyFile, objectKeyFile, requestedObjects, host, port=7734): # '' indicates bind to all IP addresses
    global serverKeys
    serverKeys = RSA.getKeys(serverKeyFile)
    global objectKeys
    objectKeys = getKeys(objectKeyFile)

    if not isinstance(port, int) or port < 0 or port > 65535:
        raise Exception("Invalid port. Should be an integer between 0 and 65535, inclusive.")
    sock = socket.socket(type=SOCK_DGRAM)
    sock.bind(socket.INADDR_ANY) # bind to any open addresss
    
    sock.connect( (host, port) )
    
    server = ServerData(host=host, port=port, sock=sock, connectionState=ClientState.HANDSHAKE_STARTED)
    
    print("Initiating connection to host '{}' and port {}".format(host, port))
    success = initiateConnection(server)
     
    if not success:
        print("Connection to host '{}' and port {} failed".format(host, port))
        return
    else:
        for object in requestedObjects:
            if server.getConnectionState() != ClientState.DATA_EXCHANGE:
                print("Disconnected from server early")
                break
            
            objectKeyHash = selectObjectKey(server, objectKeys)
            success, status = dataRequest(server, object, objectKeyHash)
            if success:
                print("Successfully retrieved object '{}'".format(object))
            else:
                print("Failed to retreive object '{}' with status '{}'".format(object, status))
    
    initiateShutdown(server)
            
"""
Initiates the connection to the server
https://github.com/AlexBlumer/AdvCompSec
:param server:      A ServerData object.

:returns:   success - a boolean representing whether the connection was successful
"""
def initiateConnection(server)

    ownPubKey, ownPrivKey = RSA.generate_key(length = 1024 ,keyFile = '') 
    hash_object = SHA256.new()
    hash_object.update(base64.b64encode(bytes(ownPubKey,'utf-8')))
    ownPubKeyHash = hash_object.digest()
    serverPubKey = RSA.importServerKey()
    sock = server.getSocket()
    sock.setTimeout(responseTimeout)
    # Send connection request
    sendMsgData = {key:ownPubKeyHash}
    sendMsg = Message(MessageType.CONNECT_REQUEST, sendMsgData)
    sendMsgBytes = sendMsg.toBytes()
    sock.send(sendMsgBytes)
    
    maxResendCount = 10
    ownDhVal = None
    while server.getConnectionState() < ClientState.DATA_EXCHANGE and resendCount < maxResendCount:
        data = None
        try:
            data = sock.recv(512)
        except socket.timeout:
            data = -1
            resendCount += 1
        
        success = False
        state = server.getConnectionState()
        if state == ClientState.HANDSHAKE_STARTED:
            if data != -1:
                success, ownDhVal = handleConnectResponse(server, data, ownPrivKey, ownPubKeyHash) # TODO timeout currently tries to resend next data, not prev
            if not success and server.getConnectionState() <= ClientState.DIFFIE_HELLMAN_SENT:
                sock.send(sendMsgBytes) # Probably a timeout, resend the request
                resendCount += 1
            else:
                resendCount = 0
        elif state == ClientState.DIFFIE_HELLMAN_SENT:
            if data != -1:
                success = handleKeyAdvertisement(server, data)
            if not success and server.getConnectionState() <= ClientState.DIFFIE_HELLMAN_SENT:
                success, _ = handleConnectResponse(server, data, ownPrivKey, ownPubKeyHash, ownDhVal)
                resendCount += 1
            else:
                resendCount = 0
        elif state == ClientState.KEYS_ADVERTISED:
            if data != -1:
                success = handleKeyAdvertisementAck(server, data)
            if not success and server.getConnectionState() <= ClientState.KEYS_ADVERTISED:
                handleKeyAdvertisement(server, data)
                resendCount += 1
            else:
                resendCount = 0
"""
Makes a data request to the server for the given object, saving it to a file with the same name as the object

:param server:      A ServerData object.
:param object:      A string identifying the object to be requested

:returns:   (success, status)
            success - a boolean representing whether or not the object was successfully retrieved
            status - a value indicating the status of the object
"""
def dataRequest(server, object, objectKeyHash):
    reqNum = generateRequestNumber()
    sock = server.getSocket()
    
    server.setRequestNumberState(reqNum, DataExchangeState.REQUEST_SENT)
    server.setRequestNumberData(reqNum, objectKeyHash)
    sessionKey = server.getSessionKey()
    
    sendMsgData = {target:object, keyHash:objectKeyHash, requestNum:reqNum}
    sendMsg = Message(MessageType.OBJECT_REQUEST, sendMsgData)
    sendMsgBytes = aesEncrypt(data=sendMsg.toBytes(), key=sessionKey)
    sock.send(sendMsgBytes)
    
    resendCount = 0
    maxResendCount = 10
    while server.getRequestNumberState(reqNum) < DataExchangeState.EXCHANGE_COMPLETE:
        data = None
        try:
            data = sock.recv(512)
        except socket.timeout:
            sock.send(sendMsgBytes)
            resendCount += 1
            continue
        
        try:
            msg = Message.fromBytes()
            handleDataResponse(server, msg)
        except: # not a valid data response, should probably be a late KeyAdvertisementAck or an objRequestAck
            success, status, recvReqNum = handleObjectRequestAck(server, data)
            if success and status != DataExchangeStatus.SENDING_DATA and recvReqNum == reqNum:
                return False, status

"""
Handles connection response messages, sending the DiffieHellman response. If called while in HANDSHAKE_STARTED, saves and updates the server's state and public key, and generates the DiffieHellman value.
If called while in another state, it merely resends the response with the given diffie hellman values

:param client:  A ClientData object.
:param data:    The bytes of the message received
:param dhVal:   The value for DiffieHellman. Optional/Ignored only if this is the first time the connection received a CONNECT_RESPONSE

:returns:   (success, dhVal)
            success is a boolean indicating whether or not the received data was a valid CONNECT_REQUEST message. False may also indicate that the retrieved values (i.e. the pubKeyHash) were invalid
            dhVal is the produced Diffie Hellman value for the exchange.
"""
def handleConnectResponse(server, data, ownPrivKey, ownPubKeyHash, dhVal=None):
    sock = server.getSocket()
    
    pubKeyHash = None
    serverDhVal = None
    dhParams = None
    try:
        unencryptedData = RSA.decrypt(data=data, privateKey=ownPrivKey)
        msg = Message.fromBytes(unencryptedData)
        pubKeyHash = msg.getPublicKeyHash()
        serverDhVal = msg.getDiffieHellmanValue()
        dhParams = msg.getDiffieHellmanParameters()
        if pubKeyHash == False or pubKeyHash == None or pubKeyHash == False or serverDhVal == None or serverDhVal == False or dhParams == None: # Not a valid CONNECT_RESPONSE. Probably an encrypted message that start with the right number
            return (False, None)
    except: # Not a proper message, likely wrong level of encryption
        if data != -1: # indicates a timeout, resend the message
            return (False, None)
    
    if server.getConnectionState() == ClientState.HANDSHAKE_STARTED:
        server.setConnectionState(ClientState.CONNECT_RESPONSE_RECEIVED)
        serverPubKey = serverKeys.get(pubKeyHash)
        server.setPubKey(serverPubKey)
        if serverPubKey == None:
            print("Cannot find server public key. Exiting...")
            server.setConnectionState(ClientState.SHUTDOWN_COMPLETE)
            return
        
        dhVal, privDhVal = DH.createDiffieHellmanValue()
        
        sessionKey = DH.createDiffieHellmanKey(sharedVal=serverDhVal, privateVal=privDhVal)
        server.setSessionKey(sessionKey)
    
    sendMsgData = {exchangeValue:dhVal}
    sendMsg = Message(MessageType.DIFFIE_HELLMAN_RESPONSE, sendMsgData)
    sendMsgBytes = RSA.encrypt(data=sendMsg.toBytes(), pubKey=server.getPubKey())
    sendMsgBytes = RSA.encrypt(data=sendMsgBytes, privKey=ownPrivKey)
    sock.send(sendMsgBytes)
    
"""
Handles key advertisement messages, sending its own key advertisement response. If called while in DIFFIE_HELLMAN_SENT, saves and updates the server's state and object keys.
If called while in another state, it merely resends the the key advertisement response

:param client:  A ClientData object.
:param data:    The bytes of the message received

:returns:   success - a boolean indicating whether or not the received data was a valid KEY_ADVERTISEMENT message. False may also indicate that the retrieved values (i.e. the keyHashes) were invalid
"""
def handleKeyAdvertisement(server, data):
    sock = server.getSocket()
    
    keyHashes = None
    try:
        unencryptedData = AES.decrypt(data=data, key=server.getSessionKey())
        msg = Message.fromBytes(unencryptedData)
        keyHashes = msg.getObjectKeyHashes()
        if keyHashes in {False, None}:
            return False
    except:
        if data != -1: # Not a timeout
            return False
    
    if server.getConnectionState() == ClientState.DIFFIE_HELLMAN_SENT:
        server.setConnectionState(ClientState.KEYS_ADVERTISED)
        server.setObjectKeyHashes(keyHashes)
    
    allowedKeys = getAllowedKeyHashes()
    sendMsgData = {"keys":allowedKeys}
    sendMsg = Message(MessageType.KEY_ADVERTISEMENT)
    sendMsgBytes = AES.encrypt(data=sendMsg.toBytes(), key=sessionKey)
    sock.send(sendMsgBytes)
    return True

"""
Handles key advertisement acks. If called while in KEYS_ADVERTISED, updates the server's state

:param client:  A ClientData object.
:param data:    The bytes of the message received

:returns:   success - a boolean indicating whether or not the received data was a valid KEY_ADVERTISEMENT message. False may also indicate that the retrieved values (i.e. the keyHashes) were invalid
"""
def handleKeyAdvertisementAck(server, data):
    try:
        unencryptedData = AES.decrypt(data=data, key=server.getSessionKey())
        msg = Message.fromBytes(unencryptedData)
        if msg.getType() != MessageType.KEY_ADVERTISEMENT_ACK:
            return False
    except:
        return False
    
    if server.getConnectionState() == ClientState.KEYS_ADVERTISED:
        server.setConnectionState(ClientState.DATA_EXCHANGE)

"""
Handles object request acks. If the status contains a failure, marks the reqNum as finished.

:param server:  A ServerData object
:param data:    The bytes of the message received

:returns:   (success, status, reqNum)
            success - a boolean indicating whether or not the received data was a valid OBJECT_REQUEST_ACK message. False may also indicate that the retrieved values (i.e. the keyHashes) were invalid
            status - the status that the object request ack gave. None if success is false
            reqNum - The request number given by the ack
"""
def handleObjectRequestAck(server, data):
    sessionKey = server.getSessionKey()
    aesDecrypt(data=data, key=sessionKey)
    
    status = None
    reqNum = None
    try:
        msg = Message.fromBytes()
        status = msg.getStatus()
        reqNum = msg.getRequestNumber()
        if status in {False, None} or reqNum in {False, None}:
            return (False, None, None)
    except:
        return (False, None, None)

    if not server.checkRequestNumberUsed(reqNum):
        return (False, None, None)
    
    if server.getConnectionState(reqNum) < DataExchangeState.EXCHANGE_COMPLETE:
        server.setConnectionState(reqNum, DataExchangeState.EXCHANGE_COMPLETE)
    
    sock = server.getSocket()
    sessionKey = server.getSessionKey()
    sendMsgData = {requestNum:reqNum}
    sendMsg = Message(MessageType.DATA_ACK, sendMsgData)
    sendMsgBytes = aesEncrypt(data=sendMsg.toBytes(), key=sessionKey)
    sock.send(sendMsgBytes)
    
    return (True, status, reqNum)
    
"""
Handles data responses. Always sends a data ack. If the request number is unfinished, saves the data to a local file and updates the request number's state.

:param client:  A ClientData object.
:param data:    The data response Message

:returns:   success - a boolean indicating whether or not the received data was a valid DATA_RESPONSE message. False may also indicate that the retrieved values (i.e. the keyHashes) were invalid
"""
def handleDataResponse(server, msg):
    reqNum = msg.getRequestNumber()
    keyHash = msg.getKeyHash()
    dataHash = msg.getObjectDataHash()
    data = msg.getObjectData()
    objectName = msg.getObjectName()
    
    if reqNum in {False, None} or keyHash in {False, None} or dataHash in {False, None} or data in {False, None} or objectName in {False, None}:
        return False
    
    if server.checkRequestNumberUsed(reqNum) == False:
        return False
    if objectName != server.getRequestNumberData(reqNum):
        return False
    key = objectKeys.get(keyHash)
    if key == None:
        return False
    
    unencryptedDataHash = aesDecrypt(data=dataHash, key=key)
    unencryptedData = aesDecrypt(data=data, key=key)
    
    preHashValue = bytearray(unencryptedData).append(bytes(objectName))
    if hash( bytes(preHashValue) ) != unencryptedDataHash: # Not the correct object
        return False
    
    if server.getRequestNumberState() == DataExchangeState.REQUEST_SENT:
        saveObject(data=unencryptedData, name=objectName)
    
    sock = server.getSocket()
    sessionKey = server.getSessionKey()
    
    sendMsgData = {requestNum:reqNum}
    sendMsg = Message(MessageType.DATA_ACK, sendMsgData)
    sendMsgBytes = aesEncrypt(data=sendMsg.toBytes(), key=sessionKey)
    sock.send(sendMsgBytes)
    
    return True
    

def initiateShutdown(server):
    server.setConnectionState(ClientState.SHUTDOWN_SENT)
    
    sock = server.getSocket()
    sock.setTimeout(responseTimeout)
    
    maxResendCount = 10
    resendCount = 0
    
    sessionKey = server.getSessionKey()
    sendMsg = Message(MessageType.SHUTDOWN_REQUEST)
    sendMsgBytes = AES.encrypt(data=sendMsg, key=sessionKey)
    
    sock.send(sendMsgBytes)
    
    while server.getConnectionState() != ServerState.SHUTDOWN_COMPLETE and resendCount < maxResendCount:
        data = None
        try:
            data = sock.recv(512)
        except socket.timeout:
            data = -1
        
        if data == -1:
            sock.send(sendMsgBytes)
        else:
            unencryptedData = AES.decrypt(data=data, key=sessionKey)
            msg = Message.fromBytes(unencryptedData)
            if msg.type == MessageType.SHUTDOWN_CLOSEE_ACK:
                server.setConnectionState(ClientState.SHUTDOWN_COMPLETE)
                sendMsg = Message(MessageType.SHUTDOWN_CLOSER_ACK)
                sendMsgBytes = AES.encrypt(data=sendMsg, key=sessionKey)
                sock.send(sendMsgBytes)
            else:
                sock.send(sendMsgBytes)
        
        resendCount += 1
    
    sock.close()

def main():
    """
    usage: python client.py OPTIONS FILE...
    
    Options:
    -h  <host> --  target host. can be IPv4 or a url
    -p <port>  --  target port. Optional, defaults to 7734
    -s <serverKeyFile> -- a file containing the public keys and their hashes for all known servers
    -o <objectKeyFile> -- a file containing the keys and their hashes for decrypting objects
    
    The program will request all files from the target server (specifiedin options), saving them locally to files of the same name.
    If no files are specified then a connection attempt will be made, then shutdown immediately
    """
    import sys
    host = None
    port = 7734
    serverKeyFile = None
    objectKeyFile = None
    files = set()
    optlist, remainingArgs = getopt(sys.argv[1:], 'h:p:s:o:')
    for optSet in optlist:
        opt = optSet[0]
        if opt == '-h':
            host = optSet[1]
        if opt == '-p':
            port = int(optSet[1])
        if opt == '-s':
            serverKeyFile = optSet[1]
        if opt == '-o':
            objectKeyFile = optSet[1]
    files = remainingArgs
    
    optionsValid = True
    if serverKeyFile == None:
        optionsValid = False
        print("Server key file must be specified. Use '-s <serverKeyFile>'")
    if host == None:
        optionsValid = False
        print("Target host must be specified. Use '-h <host>'")
    if objectKeyFile == None:
        optionsValid = False
        print("Object key file must be specified. Use '-o <objectKeyFile>'")
    
    if not optionsValid:
        return
    
    runClient(serverKeyFile, objectKeyFile, files, host, port)

if __name__ == "__main__":
    main()
from time import time
import hashlib
import json
from uuid import uuid4
from flask import Flask, jsonify, request
from urlparse import urlparse
import requests

class Blockchain(object):

    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes =set()
        #Create the first block of the chain when initialising the class
        self.new_block(previous_hash=1, proof=100)

    def new_block(self, proof, previous_hash = None):
        #Create and Add a new block to the chain
        block = {
            'index' : len(self.chain)+1,
            'timestamp': time(),
            'transaction': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        print block
        self.current_transactions=[]
        self.chain.append(block)
        return block


    def new_transaction(self, sender, receiver, amount):
        """Create a new transaction and add to list of transaction
        sender : str Address of Sender
        receiver: str Address of Receiver
        amount: int Amount value
        return <int> index of block that will store the transaction
        """
        self.current_transactions.append({
                'sender': sender,
                'receiver': receiver,
                'amount': amount
        })

        return self.last_block['index']+1

    def register_node(self,address):
        """
        Add a new node to the list of nodes
        :param address <str> Address of a node Eg:http://192.0.0.1
        :return: none
        """
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        """
        Determine if a blockchain is valid
        :param chain <list> a blockchain
        :return <bool> True if chain is valid
        """
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print last_block
            print block
            print "\n------------\n"
            #Check if hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            #Check that the proof of work
            if not self.valid_proof(block['proof'],last_block['proof']):
                return False

            last_block=block
            current_index+=1

        return True

    def resolve_conflicts(self):
        """
        This is our Consensus Algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.
        :return: <bool> True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)
        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get('http://{}/chain'.format(node))

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False

    @staticmethod
    def hash(block):
        """Create a SHA-256 hash of the block
        :param block: <dict> Block
        :return str
        """
        block_hash = json.dumps(block, sort_keys=True).encode()
        print block_hash
        return hashlib.sha256(block_hash).hexdigest()

    @property
    def last_block(self):
        #Returns the last block in the chain
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        """Simple proof of work
        find a number p such that hash(pp`) results in first 3 digits of the hash to be 000
        where p` is the previous proof of work
        """

        p=0
        while not(self.valid_proof(p,last_proof)):
            p+=1

        return p

    @staticmethod
    def valid_proof(p,last_p):
        #Checks if the hash returns first three digits as 000
        guess_string = '%s%s'%(last_p,p)
        guess_string = guess_string.encode()
        guess_p = hashlib.sha256(guess_string).hexdigest()
        return guess_p[:3] == '000'


#Instantiate a new instance
app = Flask(__name__)

#Generate a unique address  for the node
node_identifier = str(uuid4()).replace('-','')

#Instantiate BlockChain
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():

    lstblock  = blockchain.last_block
    print lstblock
    last_proof = lstblock['proof']
    print last_proof
    proof = blockchain.proof_of_work(last_proof)

    #provide incentive for mining the block
    blockchain.new_transaction(
        sender='0',
        receiver=node_identifier,
        amount=1
    )

    #add transaction to the block
    block = blockchain.new_block(proof)

    response = {
        'message': 'New block has been mined',
        'index': block['index'],
        'transaction': block['transaction'],
        'timestamp':block['timestamp'],
        'proof':block['proof'],
        'previous_hash':block['previous_hash']
    }
    return jsonify(response),200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    #Validate the request with required fields
    required = ['sender','recipient','amount']
    if not all(k in values for k in required):
        return 'Missing values in Transaction',400

    #Create a new transaction
    index = blockchain.new_transaction(values['sender'],values['recipient'],values['amount'])
    response =  {'message':'The Transaction will now be added to the block at index :'+str(index)}
    return jsonify(response),201

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }

    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    #validate node
    if nodes is None:
        return 'Error: Kindly provide a valid list of nodes', 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'The list of Nodes have been registered',#
        'Total Nodes': list(blockchain.nodes),
    }
    return jsonify(response),200

@app.route('/nodes/resolve', methods=['GET'])
def resolve_conflict():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is now authorized',
            'chain': blockchain.chain
        }
    return jsonify(response),200

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)







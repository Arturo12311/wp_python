from asyncio import open_connection, create_task, gather, IncompleteReadError, get_event_loop, Queue, sleep
from struct  import unpack, pack
from packet  import Packet
from handsakes import complete_proxify_handshake, complete_tls_handshake
from crypto import encrypt_payload, decrypt_payload
from utils import read_message, write_message
import re


class Connection:
    def __init__(self, client_reader, client_writer):

        self.port = client_writer.get_extra_info("peername")[1]

        self.client_reader = client_reader
        self.client_writer = client_writer
        self.server_reader = None
        self.server_writer = None

        self.master_key = None
        self.iv = None
        
        self.inject_listener_task = None
        self.injection_buffer = Queue()

    
    async def start(self):
        # proxify handshake
        server_host, server_port = await complete_proxify_handshake(self.client_reader, self.client_writer)
        self.server_reader, self.server_writer = await open_connection(server_host, server_port)
        print("\nPROXIFY HANDSHAKE COMPLETE", flush=True)

        # tls handshake
        try:
            self.master_key, self.iv = await complete_tls_handshake(self.client_reader, self.client_writer, self.server_reader, self.server_writer)
        except IncompleteReadError:
            return
        print("\nTLS HANDSHAKE COMPLETE\n", flush=True)

        # manage convo
        await self.manage_conversation()

    async def close(self):
        if self.client_writer:
            self.client_writer.close()
            await self.client_writer.wait_closed()
        if self.server_writer:
            self.server_writer.close()
            await self.server_writer.wait_closed()


    """CONVO HANDLER"""
    async def manage_conversation(self):     
        send_stream = create_task(self.send_stream())
        recv_stream = create_task(self.recv_stream())     
        await gather(send_stream, recv_stream) 
        if self.inject_listener_task:
            self.inject_listener_task.cancel()
            await self.inject_listener_task

    async def send_stream(self):
        count = 0
        while True:

            # read injection packet
            if not self.injection_buffer.empty():
                is_inject = True
                packet = await self.injection_buffer.get()
                header, payload = packet[:25], packet[25:]
                # print(f"INJECTED \n---\n\n", flush=True)

            # read regular packet
            else:
                is_inject = False
                try:
                    header, payload = await read_message(self.client_reader)
                except IncompleteReadError:
                    break
            
            # callibrate count
            if header[17:21] != bytes([141, 76, 212, 177]):
                count += 1
                packed_count = pack('<I', count)
                header = bytearray(header)
                header[8:12] = packed_count

            # checks if is game connection where injections should happen 
            if not self.inject_listener_task and header[17:21]==bytes([80, 143, 20, 123]):
                self.inject_listener_task = create_task(self.run_inject_listener())
                print("INJECT LISTENER ACTIVATED", flush=True)

            # Intercept and forward the packet
            await self.intercept(header, payload, "send", is_inject)
            await write_message(self.server_writer, header, payload)

    async def recv_stream(self):
        while True:
            try:
                header, payload = await read_message(self.server_reader)
            except IncompleteReadError:
                break

            # Intercept and forward the packet
            await self.intercept(header, payload, "recv")
            await write_message(self.client_writer, header, payload)


    """INTERCEPT"""
    async def intercept(self, header, payload, stream, is_inject=False):
        meta = {
            "port": self.port,
            "stream": stream,
        }
        if is_inject:
            meta["injected"] = True

        decrypted_payload = decrypt_payload(payload, self.master_key, self.iv, stream)
        # print(f"\n{list(decrypted_payload)}")

        packet = Packet(header, decrypted_payload, meta)

        # # filter
        # # if packet.header_data["name"] not in filter_list:
        # await packet.print_to_console()
        try:
            if packet.header_data["name"] not in {"TozPong", "TozPing"}:
                await packet.write_to_files()
        except UnicodeEncodeError:
            pass 
        pass
   

    """INJECT"""
    async def run_inject_listener(self):
        while True:
            command = await get_event_loop().run_in_executor(None, input)

            # drink health items
            drink_match = re.match(r'^drink\s+(\w+)(?:\s+(\d+))?$', command)

            # toggle skills auto on or off
            quest_match = re.match(r'start quest\s+(\d+)', command)

            if drink_match:
                type = drink_match.group(1)
                amount = drink_match.group(2)
                amount = int(amount) if amount else 1
                create_task(self.inject_drink(type, amount))
                print(f"Started drink injection: type={type}, amount={amount}", flush=True)
            elif quest_match:
                quest_number = quest_match.group(1)
                quest_id = None

                if quest_number == '1':
                    quest_id = 1335251852
                elif quest_number == '2':
                    quest_id = 220930238
                elif quest_number == '3':
                    quest_id = 2866979308
                elif quest_number == '4':
                    quest_id = 1973974779

                if quest_id is None:
                    print("Incorrect quest number. Please use 1, 2, 3, or 4.", flush=True)
                else:
                    create_task(self.inject_quest(quest_id))
            else:
                print("Unknown command. Please try again.", flush=True)
        

    async def inject_drink(self, type, amount=1):   
        if type == "red": 
            header = bytes([84, 79, 90, 32, 32, 0, 0, 0, 255, 255, 255, 255, 0, 18, 0, 0, 0, 65, 54, 184, 121, 255, 255, 255, 255])
            payload = bytes([0, 65, 54, 184, 121, 0, 0, 0, 0, 0, 0, 0, 0, 166, 7, 19, 81, 1])
            sleep_len = 1.2
        elif type == "blue":
            header = bytes([84, 79, 90, 32, 32, 0, 0, 0, 255, 255, 255, 255, 0, 18, 0, 0, 0, 65, 54, 184, 121, 255, 255, 255, 255])
            payload = bytes([0, 65, 54, 184, 121, 0, 0, 0, 0, 0, 0, 0, 0, 27, 157, 88, 106, 1])
            sleep_len = 32
        else:
            return

        encrypted_payload = encrypt_payload(payload, self.master_key, self.iv)
        packet = header + encrypted_payload

        for _ in range(amount):
            await self.injection_buffer.put(packet)
            await sleep(sleep_len)
        
        print(f"Finished injecting {amount} {type} drinks", flush=True)
    
    async def inject_quest(self, quest_id):
        header = bytes([84, 79, 90, 32, 32, 0, 0, 0, 172, 21, 0, 0, 0, 17, 0, 0, 0, 129, 14, 235, 111, 255, 255, 255, 255])
        payload = bytearray([0, 129, 14, 235, 111, 255, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15])
        payload[5:9] = pack("<I", quest_id)

        encrypted_payload = encrypt_payload(payload, self.master_key, self.iv)
        packet = header + encrypted_payload
        await self.injection_buffer.put(packet)

        print(f"Starting quest with id: {quest_id}", flush=True)


    
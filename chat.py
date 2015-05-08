#-------------------------------------------------------------------------------
# Name:        Chat Server and Client
# Purpose:
#
# Author:      11vanlint
#
# Version:     1.0
# Created:     08/05/2015
# Copyright:   (c) 11vanlint 2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------
#!/usr/bin/env python

from tkinter import *

import threading
import socket
import queue
import select
import sys

class ClientThread(threading.Thread):
    '''
    received_message_queue contains messages from host
    sending_message_queue is the queue for outgoing messages
    '''
    def __init__(self, host_name, identifier, port=9999):
        threading.Thread.__init__(self)
        self.daemon=True
        self.identifier=identifier
        self.host=host_name
        self.port=port
        self.running = True
        self.socket=socket.socket()

        self.received_message_queue=queue.Queue(maxsize=0)
        self.sending_message_queue=queue.Queue(maxsize=0)
        self.message_archive=[]


    def connect(self):
        try:
            self.socket.connect((self.host,int(self.port)))
            print("Connected")
        except:
            print("Error connecting:"+str(sys.exc_info()[0]))
        request=self.socket.recv(4096).decode("ascii")
        print("Request received")
        if request=="send identifier":
            print("Sending identifier")
            self.socket.send(self.identifier.encode("ascii"))
        else: raise ValueError("Expected initial identifier request, instead received %s" % request)
    def get_messages(self):
        sock, x, x = select.select([self.socket],[],[],0)
        if sock!=[]:
            message = self.socket.recv(4096).decode("ascii")
            print("Received:"+message)
            self.message_archive.append(message)
            self.received_message_queue.put(message)

    def read_and_send_messages(self):
        #read from queue and send
        if not self.sending_message_queue.empty():
            message=self.sending_message_queue.get()
            print("Sending:"+str(message))
            self.socket.send(message.encode("ascii"))

    def run(self):
        self.connect()
        while self.running:
            self.read_and_send_messages()
            self.get_messages()
    def quit(self):
        self.running=False
        self.socket.send("//discon".encode("ascii"))
        self.socket.close()

class SocketGui(Frame):
    def __init__(self,parent, receiving_queue, sending_queue):

        Frame.__init__(self, parent)
        self.pack()
        self.receiving_queue = receiving_queue
        self.sending_queue = sending_queue
        self.parent = parent
        self.parent.wm_title("Client")
        self.initGUI()
        self.parent.after(1000,self.receive)
    def initGUI(self):
        self.main_message_container = Frame(self)
        self.main_message_container.pack(padx=5,pady=5)
        self.entry_container = Frame(self)
        self.entry_container.pack(side=RIGHT,padx=5,pady=5)

        self.entry = Entry(self.entry_container, width=30)
        self.entry.pack(side=LEFT)
        self.entry.bind("<Return>", lambda x: self.send()) #ADD SENDING FUNC
        self.send_button = Button(self.entry_container, text="Send", command= self.send)
        self.send_button.pack(side=RIGHT)

        self.text = Text(self.main_message_container, width=30)
        self.text.pack(side=LEFT)
        self.scroll = Scrollbar(self.main_message_container, command=self.text.yview)
        self.scroll.pack(side=RIGHT, fill=Y)
        self.text.config(yscrollcommand=self.scroll.set)
        self.text.insert(END, "Hello\n")
        self.text.config(state="disabled")
    def send(self):
        message=self.entry.get()
        self.entry.delete(0,END)
        self.sending_queue.put(message)
    def receive(self):
        if not self.receiving_queue.empty():
            message=self.receiving_queue.get()
            self.add(message)
        self.parent.after(1000,lambda: self.receive())
        #print("hi")


    def add(self, message):

        self.text.config(state="normal")
        self.text.insert(END,str(message)+"\n")

        self.text.config(state="disabled")


class Client(threading.Thread):
    def __init__(self, message_queue, socket_address):

        threading.Thread.__init__(self)
        self.daemon = True
        self.socket, self.address= socket_address
        print(self.address)
        print("Connected to "+str(self.address))
        self.socket.send("send identifier".encode("ascii"))
        self.identifier = self.socket.recv(1024).decode("ascii")
        print("Received identifier: "+self.identifier)
        self.main_message_queue=message_queue
        self.queue = queue.Queue(maxsize=0)
        self.running = True
        self.main_message_queue.put("{} has connected".format(self.identifier))
    def __repr__(self):
        return "Client_thread with ident: {} at {}".format(self.identifier, self.address)
    def receive(self):
        (active_socket, x, x) = select.select([self.socket], [], [],0)
        if active_socket != []:
            message = self.socket.recv(4096).decode("ascii")
            print("received:"+str(message))
            if message=="//discon":
                self.main_message_queue.put("{} has disconnected".format(self.identifier))
                message=None
                self.quit()
            #insert special commands here
            else:
                message = self.identifier + ": " + message
            return message
        else:
            return None
    def run(self):

        while self.running:
            #print("running")
            data = self.receive()
            if data != None:
                self.main_message_queue.put(data)


            if not self.queue.empty():
                message=self.queue.get()
                print("Message: "+message+" going out again")
                self.socket.send(message.encode("ascii"))
            ##insert send message if queue not empty
    def quit(self):
        self.running = False
        self.socket.close()

class Host(threading.Thread):
    '''

    '''
    def __init__(self, ident, port=9999, host=socket.gethostname()):
        threading.Thread.__init__(self)
        self.daemon = True
        self.port = port
        self.host = host
        self.identifier = ident
        self.socket = socket.socket()
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        self.new_message_queue = queue.Queue(maxsize=0)
        self.client_sockets = []
        self.clients = []
        self.all_sockets = []
        self.old_messages = []
        self.running = True
        self.sending_queue=queue.Queue(maxsize=0)
        self.receiving_queue=queue.Queue(maxsize=0)
    def check_messages_and_acceptance(self):
        (ready, x, x) = select.select([self.socket], [], [],0)

        if ready != []:
            self.clients.append(Client(self.new_message_queue, self.socket.accept()))
            self.clients[len(self.clients)-1].start()
        if not self.new_message_queue.empty():

            message = self.new_message_queue.get()
            print("Message: "+message+" has reached the upper queue level")
            self.old_messages.append(message)
            self.receiving_queue.put(message)
            for i in self.clients:
                print("Message has been put in the queue of "+str(i))
                i.queue.put(message)

        #self.clients[len(clients)-1].receive()
    #def resend(self):

    def run(self):
        while self.running:
            self.check_messages_and_acceptance()
            if not self.sending_queue.empty():
                message=self.sending_queue.get()
                self.new_message_queue.put(str(self.identifier+": "+message))
    def quit(self):
        self.running = False
        self.socket.close()


class FrontPageGui(Frame):

    def __init__(self, parent):
        self.parent = parent
        Frame.__init__(self, self.parent)
        self.initGui()
        self.s = True
        self.parent.after(100, self.check_advanced_options)
        self.pack()
        #self.bind("<Return>", lambda x: self.setup())
    def initGui(self):
        self.text1 = Label(self, text="Please enter a nickname:")
        self.text1.pack(padx=3, pady=3)
        self.idententry = Entry(self)
        self.idententry.pack(padx=3, pady=3)
        self.hcchoice = StringVar()
        self.choiceframe = Frame(self)
        self.choiceframe.pack()
        self.hostbutton = Radiobutton(self.choiceframe, text="Host", variable = self.hcchoice, value = "host")
        self.clientbutton = Radiobutton(self.choiceframe, text="Client", variable = self.hcchoice, value = "client")
        self.hostbutton.pack(side=LEFT)
        self.clientbutton.pack(side=RIGHT)
        self.hostbutton.select()
        self.button=Button(self, text="Start!", command=self.setup)
        self.button.pack()
    def check_advanced_options(self):
        #print(self.hcchoice.get())
        if self.hcchoice.get()=="client" and self.s:
            self.text2 = Label(self, text="Please enter the host address:")
            self.text2.pack(padx=3, pady=3)
            self.addressentry = Entry(self)
            self.addressentry.pack(padx=3, pady=3)
            self.s = False
        elif self.hcchoice.get()=="host" and not self.s:
            self.s=True
            self.text2.destroy()
            self.addressentry.destroy()
        self.parent.after(100, self.check_advanced_options)
    def setup(self):
        #print("there")
        self.window=Toplevel()
        if self.hcchoice.get()=="client":
            self.client=ClientThread(self.addressentry.get(), self.idententry.get())
            self.client.start()
            gui=SocketGui(self.window, self.client.received_message_queue, self.client.sending_message_queue)
        elif self.hcchoice.get()=="host":
            #print("here")
            self.host=Host(self.idententry.get())
            self.host.start()
            gui=SocketGui(self.window, self.host.receiving_queue, self.host.sending_queue)


root = Tk()

gui = FrontPageGui(root)


root.mainloop()
try:
    gui.client.quit()
except:
    pass
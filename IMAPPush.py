#!/usr/bin/python
"""
So, you're confused as to why you can get email PUSHed to your mobile phone (iPhone, for example, 
but there are others, of course) or your iPod Touch (in my case) but not your computer (mac, in 
this case). I've got the Google notifier, but that checks the server, by default, every 15 mins (if 
my memory serves me correctly. I've changed that to 5 mins using the hidden preference thing (google
'gmail notifier interval' to find it) but that makes me feel a little rude. IMAP PUSH is the answer,
but the notifiers don't seem to use it. 

This script wasn't written as a replacement for the gmail notifier, but i'll certainly work on it. 
The idea behind this script was to allow for easy modification to use in your projects by looking
at this fairly complete script. If you want it to do something different, you could change the 
self.showNewMailMessages() line in waitForServer() to whatever you want. Perhaps you've got an
Arduino and you want it to light something up as soon as (well about 3-4 seconds later) the message
is sent. A fairly simple example, i know, but you get the idea.

For this script to work, you need to enable IMAP in the GMail settings. Just to make sure you got
that:

			!!! ENABLE IMAP IN YOUR GMAIL SETTINGS !!!

"""



"""
Released under the MIT/X11 License

Copyright (c) 2010 -- Chris Kirkham

 Permission is hereby granted, free of charge, to any person
 obtaining a copy of this software and associated documentation
 files (the "Software"), to deal in the Software without
 restriction, including without limitation the rights to use,
 copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the
 Software is furnished to do so, subject to the following
 conditions:

 The above copyright notice and this permission notice shall be
 included in all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
 OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 OTHER DEALINGS IN THE SOFTWARE.
"""

__version__ = '0.1'
__author__  = 'Chris Kirkham'
__URL__		= 'http://hmmtheresanidea.blogspot.com'
__credits__ = """
	* Tim's Weblog - http://blog.hokkertjes.nl/2009/03/11/python-imap-idle-with-imaplib2/ - 
	this was a great help. It got me on the right track. It taught me the Event() stuff as 
	well, so that was good.

	* Piers Lauder - http://www.cs.usyd.edu.au/~piers/python/imaplib.html - for imaplib2 
	and the documentation alongside it. Couldn't have done it without him! Thanks!
"""
__license__ = "MIT/X11"
__version__ = "1.0.1"


import threading, imaplib2, os, sys, getpass, imaplib, email, smtplib
from email.mime.text import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import Encoders


if not len(sys.argv) >= 2:
	print '* ERROR: 2 Arguments are required. Call IMAPPush.py as follows:'
	print ' '
	print 'IMAPPush.py USERNAME PASSWORD'
	print ' '
	print 'Alternatively, you can just pass your username and enter your password hidden:'
	print ' '
	print 'IMAPPush.py USERNAME					(then you\'re prompted for a password)'
	print ' '
	sys.exit(1)

#Three basic settings for you to change -- if you don't want command line input, replace the 
#sys.argv[x]s with the desired username and/or password.

YourGmailUsername = sys.argv[1]			# or 'username string'

if len(sys.argv) == 3:
	YourGmailPassword = sys.argv[2]			
else:
	YourGmailPassword = getpass.getpass()
	
#the above 4 lines could be replaced with:
#  YourGmailPassword = 'password'

ServerTimeout	  = 29 # Mins   		(leave if you're not sure)

# This is where the magic happens. Change the code below at your peril!
# Obviously if you know what you're doing, or just want to fiddle, go ahead. Don't let this warning stop you!
# But, as it is, this should work. As before, make sure you have IMAP enabled.

#'True' to enter debug mode
DEBUG = False # debugMsg() prints the parameter passed if DEBUG is True


"""
The worker class for the thread. Letting a thread wait for the server to send something allows the
main thread (if that's what you call it??) to be used for other stuff -- waiting for UI, for example.
"""
class Idler(threading.Thread):
	
	imap = imaplib2.IMAP4_SSL("imap.gmail.com") # can be changed to another server if needed

	stopWaitingEvent = threading.Event()
	#Now, this stopWaitingEvent thing -- it really does make the whole thing work. Basically, 
	#it holds a boolean value which is set and cleared using, oddly enough, the methods set() and
	#clear(). But, the good thing about it is that it has another method, wait(), which holds 
	#execution until it has been set(). I cannot thank threading.Event() enough, I really couldn't
	#have done it without you!

	knownAboutMail = [] # will be a list of IDs of messages in the inbox
	killNow = False # stops execution of thread to allow propper closing of conns.


	"""
	Initialise (sorry, I'm from the UK) everything to get ready for PUSHed mail.
	"""
	def __init__(self, GMailUsername, GMailPassword):
		
		os.system('clear')
		debugMsg('DEBUG is ENABLED')
		debugMsg('__init__() entered')
				
		try:
			#establish connection to IMAP Server
			self.imap.LOGIN(GMailUsername, GMailPassword)
			self.imap.SELECT("INBOX")
			
			#get the IDs of all messages in the inbox and put in knowAboutMail
			typ, data = self.imap.SEARCH(None, 'ALL')
			self.knownAboutMail = data[0].split()
			
			#now run the inherited __init__ method to create thread
			threading.Thread.__init__(self)
			
		except: #Uh Oh, something went wrong
			print 'ERROR: IMAP Issue. It could be one (or more) of the following:'
			print '- The impalib2.py file needs to be in the same directory as this file'
			print '- You\'re not connected to the internet'
			print '- Google\'s mail server(s) is/are down'
			print '- Your username and/or password is incorrect'
			sys.exit(1)
			
		debugMsg('__init__() exited')


	"""
	The method invoked when the thread id start()ed. Enter a loop executing waitForServer()
	untill kill()ed. waitForServer() can, and should, be continuously executed to be alerted
	of new mail.
	"""
	def run(self):
		debugMsg('run() entered')	
		
		#loop until killNow is set by kill() method
		while not self.killNow:
			self.waitForServer()	
			
		debugMsg('run() exited')
	
	
	"""
	Name says it all really: get (just) the specified header fields from the server for the 
	specified message ID.
	"""
	def getMessageHeaderFieldsById(self, id, fields_tuple):
		debugMsg('getMessageHeaderFieldsById() entered')
		
		#get the entire header
		typ, header = self.imap.FETCH(id, '(RFC822.HEADER)')
		
		#get individual lines
		headerlines = header[0][1].splitlines()
		
		#get the lines that start with the values in fields_tuple
		results = {}
		for field in fields_tuple:
			results[field] = ''
			for line in headerlines:
				if line.startswith(field):
					results[field] = line
					
		debugMsg('getMessageHeaderFieldsById() exited')
		return results #which is a dictionary containing the the requested fields
		
		
	"""
	The main def for displaying messages. It draws on getMessageHeaderFieldsById() and growlnotify()
	to do so.
	"""
	def showNewMailMessages(self):
		debugMsg('showNewMailMessages() entered')
		
		#get IDs of all UNSEEN messages 
		typ, data = self.imap.SEARCH(None, 'UNSEEN')
		
		debugMsg('data - new mail IDs:')
		debugMsg(data, 0)
		
		for id in data[0].split():
			if not id in self.knownAboutMail:
				
				#get From and Subject fields from header
				headerFields = self.getMessageHeaderFieldsById(id, ('From', 'Subject'))
				
				debugMsg('headerFields dict. (from showNewMailMessage()):')
				debugMsg(headerFields, 0)
				
				#notify
				lastMessageRecieved(YourGmailUsername, YourGmailPassword)
				#add this message to the list of known messages
				self.knownAboutMail.append(id)
				
		debugMsg('showNewMailMessages() exited')


	"""
	Called to stop the script. It stops the continuous while loop in run() and therefore
	stops the thread's execution.
	"""
	def kill(self):
		self.killNow = True # to stop while loop in run()
		self.timeout = True # keeps waitForServer() nice
		self.stopWaitingEvent.set() # to let wait() to return and let execution continue


	"""
	This is the block of code called by the run() method of the therad. It is what does all 
	the waiting for new mail (well, and timeouts).
	"""
	def waitForServer(self):
		debugMsg('waitForServer() entered')
		
		#init
		self.newMail = False
		self.timeout = False
		self.IDLEArgs = ''
		self.stopWaitingEvent.clear()
		
		def _IDLECallback(args):
			self.IDLEArgs = args
			self.stopWaitingEvent.set()
			#_IDLECallack() is entered when the IMAP server responds to the IDLE command when new
			#mail is received. The self.stopWaitingEvent.set() allows the .wait() to return and
			#therefore the rest of waitForServer().
			
			
		#attach callback function, and let server know it should tell us when new mail arrives	
		self.imap.idle(timeout=60*ServerTimeout, callback=_IDLECallback)

		#execution will stay here until either:
		# - a new message is received; or
		# - the timeout has happened 
		#   	- we set the timout -- the RFC says the server has the right to forget about 
		#	  	  us after 30 mins of inactivity (i.e. not communicating with server for 30 mins). 
		#	  	  By sending the IDLE command every 29 mins, we won't be forgotten.
		# - Alternatively, the kill() method has been invoked.
		self.stopWaitingEvent.wait()
		
		#self.IDLEArgs has now been filled (if not kill()ed)
		
		if not self.killNow: # skips a chunk of code to sys.exit() more quickly.
			
			if self.IDLEArgs[0][1][0] == ('IDLE terminated (Success)'):
			# This (above) is sent when either: there has been a timeout (server sends); or, there
			# is new mail. We have to check manually to see if there is new mail. 
				
				typ, data = self.imap.SEARCH(None, 'UNSEEN') # like before, get UNSEEN message IDs
				
				debugMsg('Data: ')
				debugMsg(data, 0)
				
				#see if each ID is new, and, if it is, make newMail True
				for id in data[0].split():
					if not id in self.knownAboutMail:
						self.newMail = self.newMail or True
					else:
						self.timeout = True 
						# gets executed if there are UNSEEN messages that we have been notified of, 
						# but we haven't yet read. In this case, it response was just a timeout.
						
				if data[0] == '': # no IDs, so it was a timeout (but no notified but UNSEEN mail)
					self.timeout = True

			#now there has either been a timeout or a new message -- Do something...
			if self.newMail:
				debugMsg('INFO: New Mail Received')
				self.showNewMailMessages()


			elif self.timeout:
				debugMsg('INFO: A Timeout Occurred')
			
		debugMsg('waitForServer() exited')


"""
Simple procedure to output debug messages nicely.
"""
def debugMsg(msg, newline=1):
	global DEBUG
	if DEBUG:
		if newline:
			print ' '
		print msg


"""
Procedure to output the subject and from of the last email recieved
"""
def lastMessageRecieved(YourGmailUsername, YourGmailPassword):
	mail = imaplib.IMAP4_SSL('imap.gmail.com')
	(retcode, capabilities) = mail.login(YourGmailUsername,YourGmailPassword )
	mail.list()
	mail.select('inbox')
	(retcode, messages) = mail.search(None, 'X-GM-RAW', 'in:unread')
	n = 0
	if retcode == 'OK':
		print ('Processing the new recieved mail...')
		messages = messages[0].split() 
		typ, data = mail.fetch(messages[-1],'(RFC822)')
		for response_part in data:
			if isinstance(response_part, tuple):
				typ, data = mail.store(messages[-1],'-FLAGS','\\Seen') # TO let the message like unread, because we are only listing... we are not viewing the details
				original = email.message_from_string(response_part[1].decode("utf-8",'ignore'))
				print ('New email... FROM: ' + original['From'] + ' - SUBJECT:' + original['Subject'])

	mail.close()
	mail.logout()
	print('Type \'q\' followed by [ENTER] to quit or type \'u\' followed by [ENTER] to update list of unreaded mails (without spam or social mails): ')


"""
Procedure to output a list with the subject and from of unread mails
"""
def unreadList(YourGmailUsername, YourGmailPassword):
	mail = imaplib.IMAP4_SSL('imap.gmail.com')
	(retcode, capabilities) = mail.login(YourGmailUsername,YourGmailPassword )
	mail.list()
	mail.select('inbox')

	n=0
	gmail_search = "category:primary" 
	(retcode, messages_primary) = mail.search(None, 'X-GM-RAW', 'category:primary')
	(retcode, messages_unread) = mail.search(None, 'X-GM-RAW', 'in:unread')
	if retcode == 'OK':
		messages_primary = messages_primary[0].split()
		messages_unread = messages_unread[0].split()
		messages = []
		for message in messages_primary:
			if message in messages_unread:
				messages.append(message)


		#print (messages)
		print ('Processing unread mails...')
		for num in messages :
			n=n+1
			typ, data = mail.fetch(num,'(RFC822)')
			for response_part in data:
				if isinstance(response_part, tuple):
					typ, data = mail.store(num,'-FLAGS','\\Seen') # TO let the message like unread, because we are only listing... we are not viewing the details
					original = email.message_from_string(response_part[1].decode("utf-8",'ignore'))
					print ('[' + str(n) + '] FROM: ' + original['From'] + ' - SUBJECT:' + original['Subject'])
	mail.close()
	mail.logout()


"""
Function to send a mail
"""
def sendMail(content, to, subject, file_names, YourGmailUsername, YourGmailPassword):
	smtp_ssl_host = 'smtp.gmail.com'
	smtp_ssl_port = 465
	username = YourGmailUsername
	password = YourGmailPassword
	msg = MIMEMultipart()
	msg['Subject'] = subject
	msg['From'] = YourGmailUsername
	msg['To'] = to
	body = MIMEText(content)
	msg.attach(body)
	server = smtplib.SMTP_SSL(smtp_ssl_host, smtp_ssl_port)
	server.login(username, password)
	for file in file_names:
		#left validate every file here
		part = MIMEBase('application', "octet-stream")
		part.set_payload( open(file,"rb").read() )
		Encoders.encode_base64(part)
		part.add_header('Content-Disposition', 'attachment; filename="%s"'
					   % os.path.basename(file))
		msg.attach(part)
	try:
		server.sendmail(YourGmailUsername, to, msg.as_string())
		server.quit()
		return 1
	except:
		server.quit()
		return 0


"""
Main bit of code to get the ball rolling. It starts the thread and waits for 'q' to be input.
That's it. Nice and simple.
"""
def main():
	global YourGmailUsername
	global YourGmailPassword
	
	idler = Idler(YourGmailUsername, YourGmailPassword)
	idler.start()
	
	print '* Waiting for mail...'
	q = ''
	while not q == 'q':
		q = raw_input('Type \'q\' followed by [ENTER] to quit or type \'u\' followed by [ENTER] to update list of unreaded mails (without spam or social mails) or  type \'s\' followed by [ENTER] to send a mail:')
		if(q == 'u'):	
			unreadList(YourGmailUsername, YourGmailPassword)
		elif(q == 's'):
			#left validate entries here
			to = raw_input('Text the mails, following as \',\', example (example1@yopmail.com,example2@yopmail.com)\n')
			subject = raw_input('Enter the subject\n')
			content = raw_input('Put the content of the message here:\n')
			file_names =[]
			file = raw_input('Put the path of file to attach (if you dont want add more files only text \'q\')\n')
			while(file != 'q'):
				file_names.append(file)
				file = raw_input('Put the path of file to attach (if you dont want add more files only text \'q\')\n')
			if sendMail(content, to, subject, file_names, YourGmailUsername, YourGmailPassword):
				print 'Email send'
			else:
				print 'Email not send'

	idler.kill()	
	idler.imap.CLOSE()
	idler.imap.LOGOUT()
	sys.exit()



if __name__ == '__main__': # then this script is being run on its own, i.e. not imported
	main()
else:
	print 'I don\'t think you ment to import this'
	sys.exit(1)
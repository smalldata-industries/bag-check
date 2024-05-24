'''
##### IMPORTANT - READ BEFORE USING #####

This fixity check automation tool is being provided as-is, with no guarantees or warranties.
It is intended to be used as a starting point for those looking to automate fixity checks on their digital collections.

Please only use this script in a tightly controlled environment, as the fixity check database is not password protected,
and if you choose to use the email feature, the password for the email account is hard-coded into the script. This is generally
not a secure practice, and should only be used in a trusted environment.
'''


### user editable settings

### do you want to send email notifications?
sendemail = False

### email settings
email = ''   	# the email account you want to send reports from
password = ''  	#  password for the above account
recipient = ''	# recipient email address
cc = ''			# cc email address
smtp_server = ''
smtp_port = 0\




#!/usr/bin/env python3          
import argparse
import datetime
import pathlib
import sqlite3
import os
import glob
import sys
import subprocess
from sqlite3 import Error
import bagitFix	as bagit # this is a modified version of the bagit library that includes a fix for a bug in the original library that prevented full validation and always defaulted to "quick"	validation
from fpdf import FPDF
import smtplib, ssl
from email.mime.multipart import MIMEMultipart 
from email.mime.text import MIMEText 
from email.mime.application import MIMEApplication

parser = argparse.ArgumentParser(description="Python script for running regular fixity checks on a series of BagIt bags")
parser.add_argument('-i', '--input', type=pathlib.Path, required=True, help='The absolute path to the the root directory or volume to be scanned')
parser.add_argument('-d', '--depth', type=int, required=True, help='What level of recursion to find bags at')
args = parser.parse_args()


dbfilename = str(datetime.datetime.now())
dbfilename = dbfilename.replace(':', '-')
dbfilename = dbfilename.replace(' ', '_')
dbfilename = dbfilename+".db"
# db_global = "./db/"+dbfilename
script_dir = os.path.dirname(os.path.realpath(__file__))
db_directory = os.path.join(script_dir, 'db')
db_global = os.path.join(db_directory, dbfilename)


dict_of_failures = {}

def create_connection(db_file):
	conn = None
	try:
		conn = sqlite3.connect(db_file)
		return conn
	except Error as e:
		print(e)

	return conn

def create_table(conn, create_table_sql):
	try:
		c = conn.cursor()
		c.execute(create_table_sql)
	except Error as e:
		print(e)


def main():
	runNumGlobal = 1
	db_list = glob.glob('./db/*.db')
	db_list.sort()
	howmanydbs = len(db_list)-1
	

	if howmanydbs >= 0:
		lastrundb = db_list[howmanydbs]
		conn2 = create_connection(lastrundb)
		if conn2 is not None:
			cursor=conn2.cursor()
			cursor.execute("SELECT * FROM fixityRuns")
			lastrunnum = (cursor.fetchall()[0][1])
			runNumGlobal = lastrunnum+1
			print(lastrunnum)
		else:
			print("Error! cannot connect to previous db.")
			


	sql_create_runs_table = """ CREATE TABLE IF NOT EXISTS fixityRuns (
									id integer PRIMARY KEY,
									run_num integer,
									begin_date text,
									end_date text,
									how_many_bags_checked integer,
									how_many_bags_valid integer,
									how_many_bags_missing integer,
									how_many_bags_invalid integer
								); """

	sql_create_bags_table = """CREATE TABLE IF NOT EXISTS bags (
									id integer PRIMARY KEY,
									runid integer,
									filepath text,
									checkdatetime text,
									isbag text,
									validation_outcome text,
									BagError text,
									ValidationError text,
									FOREIGN KEY (runid) REFERENCES fixityRuns (id)
								);"""

	# create a database connection
	conn = create_connection(db_global)

	# create tables
	if conn is not None:
		# create projects table
		create_table(conn, sql_create_runs_table)

		# create tasks table
		create_table(conn, sql_create_bags_table)
		conn.text_factory = str
		c = conn.cursor()
		startdatetime = datetime.datetime.now()		
		params = [runNumGlobal,startdatetime,None,None,None,None,None]
		c.execute('insert into fixityRuns values (NULL,?,?,?,?,?,?,?)', params)
		conn.commit()

	else:
		print("Error! cannot create the database connection.")



def crawler(directory):
	depth = args.depth
	stuff = os.path.abspath(os.path.expanduser(os.path.expandvars(directory)))


	conn = sqlite3.connect(db_global)
	conn.text_factory = str
	c = conn.cursor()

	for root,dirs,files in os.walk(str(stuff)):
		if root[len(stuff):].count(os.sep) == depth:
			params = [root,None,None,None,None,None]
			# insert full path and file name into table
			c.execute('insert into bags values (NULL,NULL,?,?,?,?,?,?)', params)
			conn.commit()

def bagchecker():
	conn = sqlite3.connect(db_global)
	conn.text_factory = str
	c = conn.cursor()
	c.execute('SELECT * FROM bags')
	alltherows = c.fetchall()
	counter = 1
	for row in alltherows:
		bagpath = row[2]
		currentid = row[0]
		now = datetime.datetime.now()
		bag = None
		try:
			bag = bagit.Bag(bagpath)
			print("Checking: %s"%(bagpath,))
			try:
				validation_check = bag.validate()
				if validation_check:
					print ("validated")
					validation_check = "Valid"
					c.execute('UPDATE bags SET validation_outcome = ?, checkdatetime = ? WHERE id = ?',(validation_check, now, currentid))
				else:
					print ("not validated")
				conn.commit()
			except bagit.BagValidationError as e:
				print (e)
				c.execute('UPDATE bags SET validation_outcome = ?, ValidationError = ?, checkdatetime = ? WHERE id = ?',("Invalid", str(e), now, currentid))
				conn.commit()
				# add entry to dict_of_failures with absolute path to given bag as key, and value as the error message
				
				dict_of_failures[os.path.abspath(bagpath)] = str(e)
		except bagit.BagError as e:
			print (e)
			c.execute('UPDATE bags SET BagError = ?, checkdatetime = ? WHERE id = ?',(str(e), now, currentid))
			conn.commit()
			dict_of_failures[os.path.abspath(bagpath)] = str(e)

def makeandsendreport():
	conn = create_connection(db_global)
	conn.text_factory = str
	c = conn.cursor()
	endtime = datetime.datetime.now()


	db_list = glob.glob(db_directory + '/*.db')
	db_list.sort()
	lastdbindex = len(db_list)-2
	lastdb = db_list[lastdbindex]

	conn2 = create_connection(lastdb)
	conn2.text_factory = str
	c2 = conn2.cursor()

	c2.execute('SELECT COUNT(*) from bags')
	numberofbagslasttime = c2.fetchone()[0]

	c2.execute('SELECT * FROM fixityRuns')
	lastrandate = c2.fetchone()[3]

	print ("Number of bags that existed when last fixity check was run: %s"%(numberofbagslasttime,))


	c.execute('SELECT COUNT(*) from bags')
	numberofbagsthistime = c.fetchone()[0]

	bagsadded = numberofbagsthistime-numberofbagslasttime

	if bagsadded >= 0:
		print("Number of bags that have been added since the last fixity check: %s"%(bagsadded,))

	print("Current total number of bags: %s"%(numberofbagsthistime,))

	c.execute('SELECT COUNT(*) from bags where validation_outcome is "Valid"')
	validbags = c.fetchone()[0]

	print("Number of valid bags: %s"%(validbags,))

	c.execute('SELECT COUNT(*) from bags where validation_outcome is "Invalid"')
	invalidbags = c.fetchone()[0]
	print("Number of invalid bags: %s"%(invalidbags,))

	c.execute('SELECT COUNT(*) from bags where BagError is not Null')
	bagswitherrors = c.fetchone()[0]
	print("Number of bags with errors: %s"%(bagswitherrors,))



	#how many missing
	c2.execute('SELECT * FROM bags')
	alltherows = c2.fetchall()
	missingcounter = 0
	presentcounter = 0
	for row in alltherows:
		oldpath = row[2]
		c.execute('SELECT * from bags where filepath is ?',(oldpath,))
		
		try:
			newpath = c.fetchone()[2]
			if newpath == oldpath:
				presentcounter = presentcounter+1
			else:
				missingcounter = missingcounter+1
		except:
			missingcounter = missingcounter+1
	print("Number of bags from last check that are still present: %s"%(presentcounter,))
	print("Number of bags that have disappeared since last check: %s"%(missingcounter,))


	c.execute('UPDATE fixityRuns SET end_date = ? WHERE id = ?',(endtime,1))
	conn.commit()

	##### PDF STUFF

	#### parsing timestamp and turning it into something human readable for the report
	dayint = datetime.datetime.now().weekday()
	daylist = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
	day = daylist[dayint]
	monthint = datetime.datetime.now().month-1
	monthlist = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
	month = monthlist[monthint]
	daynum = datetime.datetime.now().strftime("%d")

	# save FPDF() class into a 
	# variable pdf
	pdf = FPDF()
	  
	# Add a page
	pdf.add_page()
	  
	# set style and size of font 
	# that you want in the pdf
	pdf.set_font("Arial", size = 18)
	  
	# add your logo here - just place in the same folder as this script, change the filename below, and uncomment the line
	# pdf.image("example-logo.jpg",10,10,100)

	pdf.ln(20)
	pdf.set_text_color(128)

	# create a cell
	pdf.cell(200, 10, txt = "Fixity check report", 
			 ln = 1, align = 'L')
	pdf.ln(5)
	

	c.execute('SELECT * from fixityRuns')
	runnumber = c.fetchone()[1]
	c.execute('SELECT * from fixityRuns')
	began = c.fetchone()[2]
	c.execute('SELECT * from fixityRuns')
	ended = c.fetchone()[3]



	beganDays = datetime.datetime.strptime(began, "%Y-%m-%d %H:%M:%S.%f")
	endedDays = datetime.datetime.strptime(ended, "%Y-%m-%d %H:%M:%S.%f")

	duration = endedDays-beganDays


	pdf.multi_cell(200, 10, txt = "Today is %s, %s %s, and \
 fixity check number %s has been completed."%(
	day,month,daynum,runnumber), align = 'L')
	pdf.ln(5)
	### condition for when all is well
	if bagswitherrors == 0 and invalidbags == 0 and missingcounter == 0:
		pdf.cell(200, 10, txt = "Status: good", 
				 ln = 1, align = 'L')
	elif missingcounter == 0:
		pdf.set_text_color(255,0,0)
		pdf.cell(200, 10, txt = "Status: ALERT!", 
				 ln = 1, align = 'L')
		# add another cell
	
	pdf.set_text_color(128)

	
	pdf.ln(10)
	pdf.cell(200, 10, txt = "Check began: %s"%(began,),  ln = 1, align = 'L')
	pdf.ln(5)
	pdf.cell(200, 10, txt = "Check ended: %s"%(ended,),  ln = 1, align = 'L')
	pdf.ln(5)
	pdf.cell(200, 10, txt = "Number of new bags since last scan: %s"%(bagsadded,),  ln = 1, align = 'L')
	pdf.ln(5)
	pdf.cell(200, 10, txt = "Total bags scanned: %s"%(numberofbagsthistime,),  ln = 1, align = 'L')
	pdf.ln(5)
	pdf.cell(200, 10, txt = "Valid bags: %s"%(validbags,),  ln = 1, align = 'L')
	pdf.ln(5)
	if invalidbags != 0:
		pdf.set_text_color(255,0,0)
	pdf.cell(200, 10, txt = "Invalid bags: %s"%(invalidbags,),  ln = 1, align = 'L')
	pdf.set_text_color(128)
	pdf.ln(5)
	if bagswitherrors != 0:
		pdf.set_text_color(255,0,0)
	pdf.cell(200, 10, txt = "Bags with errors: %s"%(bagswitherrors,),  ln = 1, align = 'L')
	pdf.ln(5)

	## iterate on the dict_of_failures and add to the pdf
	for key, value in dict_of_failures.items():
		# set font size to 12
		pdf.set_font("Arial", size = 10)
		# sent line height
		pdf.ln(5)
		pdf.set_text_color(255,0,0)
		pdf.cell(200, 10, txt = "Bag: %s"%(key,),  ln = 1, align = 'L')
		pdf.set_text_color(128)
		pdf.multi_cell(200, 10, txt = "Error: %s"%(value,), align = 'L')
		pdf.ln(5)


		  
	# here we save the pdf with name .pdf in the db directory
	pdf.output(db_directory+"/"+dbfilename+".pdf")
	# pdf.output(dbfilename+".pdf")




	if sendemail:
		# formulate and send the email 
		subjectTimestamp = str(datetime.datetime.now())

		message = MIMEMultipart('mixed')
		message['From'] = 'Contact <{sender}>'.format(sender = email)
		message['To'] = recipient
		message['CC'] = cc
		message['Subject'] = 'Fixity check finished %s'%(subjectTimestamp,)

		msg_content = 'A collection-wide fixity check was just run - see attached PDF report for results...\n'
		body = MIMEText(msg_content, 'html')
		message.attach(body)

		attachmentPath = dbfilename+".pdf"

		try:
			with open(attachmentPath, "rb") as attachment:
				p = MIMEApplication(attachment.read(),_subtype="pdf")	
				p.add_header('Content-Disposition', "attachment; filename= %s" % attachmentPath.split("\\")[-1]) 
				message.attach(p)
		except Exception as e:
			print(str(e))

		msg_full = message.as_string()

		context = ssl.create_default_context()


		

		with smtplib.SMTP(smtp_server, smtp_port) as server:
			server.ehlo()  
			server.starttls(context=context)
			server.ehlo()
			server.login(email, password)
			server.sendmail(email, message['To'].split(";") + (message['CC'].split(";") if message['CC'] else []),
						msg_full)
			server.quit()

		print("email sent out successfully")
	else:
		print("done!")




if __name__ == '__main__':
	main()
	crawler(args.input)
	bagchecker()
	makeandsendreport()

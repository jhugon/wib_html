#!/usr/bin/env python2

import os
import os.path
import subprocess
import datetime
import time
import re

class NoWIBError(Exception):
  pass

class WIBDNDWarning(Warning):
  pass

class WIBHTML(object):

  def __init__(self,wib_uris,sleep_interval):

  
    self.wib_uris = wib_uris

    self.sleep_interval = sleep_interval
  
    self.wib_html_dir = os.path.dirname(os.path.realpath(__file__))
    self.temp_dir = os.path.join(self.wib_html_dir,"temp_dir/")
    self.out_dir = os.path.join(self.wib_html_dir,"html_output/")
    self.individual_out_dir = os.path.join(self.out_dir,"wibs")
    self.temp_fn = os.path.join(self.temp_dir,"status.html")

    self.status_script_fn = "butool_scripts/html_status.script"
    self.status_script_fn = os.path.join(self.wib_html_dir,self.status_script_fn)

    self.check_dnd_script_fn = "butool_scripts/check_dnd.script"
    self.check_dnd_script_fn = os.path.join(self.wib_html_dir,self.check_dnd_script_fn)

    self.empty_html_fn = os.path.join(self.wib_html_dir,"html_templates/empty.html")

    self.main_page_template_fn = os.path.join(self.wib_html_dir,"html_templates/index.html")
    self.main_page_fn = os.path.join(self.out_dir,"index.html")

    self.wib_locations = {}
    self.wib_locations_simple = ["coldbox","dsras","msras","usras","dsdas","usdas","msdas",None,None,"vst"]
    for i, loc in enumerate(self.wib_locations_simple):
      if loc is None:
        continue
      for j in range(1,6):
        name = "np04-wib-{0:03d}".format(i*100+j)
        self.wib_locations[name] = loc

  def get_wib_name(self,wib_uri):
    if "192.168.200." in wib_uri:
      vst_num = wib_uri.split(".")[-1].strip(" ")
      vst_num = int(vst_num)
      wib_uri = "np04-wib-{0}".format(900+vst_num)
    return wib_uri

  def check_dnd(self,wib_uri):
    """
    Check if do-not-distrub bit is set for a given wib
    """
    args = ["BUTool.exe","-w",wib_uri,"-X",self.check_dnd_script_fn]
    output = subprocess.check_output(args,cwd=self.temp_dir)
    if "0xdead" in output and "0xbeef" in output:
      raise NoWIBError()
    match = re.search(r"SYSTEM.SLOW_CONTROL_DND: ([0-9a-zA-Z]+)\n",output)
    if match:
      regval = int(match.group(1),16) #is hex
      if regval > 0:
        raise WIBDNDWarning
    else:
      print output
      raise Exception("Above output didn't match expected slow control regex")
  
  def get_status(self,wib_uri):
    args = ["BUTool.exe","-w",wib_uri,"-X",self.status_script_fn]
    output = subprocess.check_output(args,cwd=self.temp_dir)
    if "0xdead" in output and "0xbeef" in output:
      raise NoWIBError()
          
  def copy_modify_status_html(self,wib_uri):
    wib_uri = self.get_wib_name(wib_uri)
    title = "WIB Status Page for "+str(wib_uri)
    thistime = datetime.datetime.now().replace(microsecond=0).isoformat(' ')
    instr = ""
    with open(self.temp_fn) as infile:
      instr = infile.read()
    newstr = "<h1>{0}</h1>\n<p>Updated at {1} Geneva time</p>\n".format(title,thistime)
    outstr = instr.replace("<body>","<body>\n"+newstr)
    outfn = os.path.join(self.individual_out_dir,wib_uri)+".html"
    with open(outfn,'w') as outfile:
      outfile.write(outstr)

  def annotate_page_on_error(self,wib_uri,busy):
    """
    if busy then put busy message, else no wib message
    """
    thistime = datetime.datetime.now().replace(microsecond=0).isoformat(' ')
    wib_name = self.get_wib_name(wib_uri)
    fn = os.path.join(self.individual_out_dir,wib_name)+".html"
    text = ""
    try:
      with open(fn) as infile:
        text = infile.read()
    except IOError:
      with open(self.empty_html_fn) as infile:
        text = infile.read()
    hasbusydiv = False
    hasnowibdiv = False
    if "id=busyerr" in text:
      hasbusydiv = True
    if "id=nowiberr" in text:
      hasnowibdiv = True
    newtext = ""
    if busy:
      newtext = "<div id=busyerr><p>WIB was busy at {0} Geneva time<p></div>".format(thistime)
    else:
      newtext = "<div id=nowiberr><p>WIB not found at {0} Geneva time<p></div>".format(thistime)
    if hasbusydiv:
      if busy:
        text = re.sub(r"<div id=busyerr>.*?</div>",newtext,text)
      else:
        text = re.sub(r"<div id=busyerr>.*?</div>",r"\g<0>"+"\n"+newtext,text)
    elif hasnowibdiv:
      if busy:
        text = re.sub(r"<div id=nowiberr>.*?</div>",r"\g<0>"+"\n"+newtext,text)
      else:
        text = re.sub(r"<div id=nowiberr>.*?</div>",newtext,text)
    else:
      text = text.replace("</h1>","</h1>\n"+newtext+'\n')
    with open(fn,'w') as outfile:
      outfile.write(text)

  def update_individual_pages(self):
    for wib_uri in self.wib_uris:
      try:
        os.remove(self.temp_fn)
      except OSError:
        pass
      try:
        try:
          self.check_dnd(wib_uri)
        except WIBDNDWarning:
          #print "WIB {0} busy".format(wib_uri)
          self.annotate_page_on_error(wib_uri,True)
        else:
          self.get_status(wib_uri)
          self.copy_modify_status_html(wib_uri)
      except NoWIBError:
        #print "WIB {0} not found".format(wib_uri)
        self.annotate_page_on_error(wib_uri,False)

  def make_main_page(self):
    text = ""
    with open(self.main_page_template_fn) as infile:
      text = infile.read()

    wibnames = [self.get_wib_name(wiburi) for wiburi in self.wib_uris]
    wibnames.sort()
    wibnames.reverse()
    for wibname in wibnames:
      indfn = os.path.join(self.out_dir,"wibs/{0}.html".format(wibname))
      indtext = ""
      with open(indfn) as indf:
        indtext = indf.read()
      wibstatus = "goodwib"
      if "id=nowiberr" in indtext:
        wibstatus = "nowib"
      elif "id=busyerr" in indtext:
        wibstatus = "busywib"
      wibloc = self.wib_locations[wibname]
      newtext = '<p><a href="./wibs/{0}.html" class="{1}">{2}</a></p>'.format(wibname,wibstatus,wibname)
      regex = r"<td id={0}>".format(wibloc)
      text = re.sub(regex,r"\g<0>"+"\n"+" "*10+newtext,text)

    with open(self.main_page_fn,'w') as outfile:
        outfile.write(text)

  def run(self):
    while True:
      self.update_individual_pages()
      self.make_main_page()
      time.sleep(self.sleep_interval)

if __name__ == "__main__":

  wib_uris = [
    #"192.168.200.1",
    "192.168.200.2",
    #"192.168.200.3",
    #"192.168.200.4",
    "192.168.200.5",
  ]
  for i in range(7):
    for j in range(1,6):
      wib_uris += ["np04-wib-{0:03d}".format(i*100+j)]

  wibhtml = WIBHTML(wib_uris,120)
  wibhtml.run()


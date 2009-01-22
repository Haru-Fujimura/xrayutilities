#module for handling files stored in the EDF data format developed by the ESRF

import numpy
import re
import struct
import tables
import os
import os.path

edf_kv_split=re.compile(r"\s*=\s*") #key value sepeartor for header data
edf_eokv = re.compile(r";") #end of line for a header
#regular expressions for several ASCII representations of numbers
edf_integer_value = re.compile(r"\d+")
edf_float_value = re.compile(r"[+-]*\d+\.*\d*")
edf_float_e_value = re.compile(r"[+-]*\d+\.\d*e[+-]*\d*")
edf_id01_motor_prefix = re.compile(r"ESRF_ID01_.*")
edf_id01_motor_motor = re.compile(r"PSIC_.*")
edf_name_start_num=re.compile(r"^\d")

#dictionary mapping EDF data type keywords onto struct data types
DataTypeDict = {"SignedByte":"b",
                "SignedShort":"h",
                "SignedInteger":"i",
                "SignedLong":"l",
                "FloatValue":"f",
                "DoubleValue":"d",
                "UnsignedByte":"B",
                "UnsignedShort":"H",
                "UnsignedInt":"I",
                "UnsignedLong":"L"}


class EDFFile(object):
    def __init__(self,fname,**keyargs):
        """
        
        required arguments:
        fname ................ name of the EDF file
        
        optional keyword arguments:
        nxkey ................ name of the header key that holds the number of points in x-direction
        nykey ................ name of the header key that holds the number of points in y-direction
        dtkey ................ name of the header key that holds the datatype for the binary data
        path ................. path to the EDF file
        """
        
        self.filename = fname
        if keyargs.has_key("path"):
            self.full_filename = os.path.join(keyargs["path"],fname)
        else:
            self.full_filename = fname
            
        try:
            self.fid = open(self.full_filename,"r")
        except:
            print "cannot open file %s" %(self.full_filename)
        

        #evaluate keyword arguments
        if keyargs.has_key("nxkey"):
            self.nxkey = keyargs["nxkey"]
        else:
            self.nxkey = "Dim_1"

        if keyargs.has_key("nykey"):
            self.nykey = keyargs["nykey"]
        else:
            self.nykey = "Dim_2"

        if keyargs.has_key("dtkey"):
            self.dtkey = keyargs["dtkey"]
        else:
            self.dtkey = "DataType"
            
        #create attributes for holding data
        self.header = {}
        self.data = None
    
        
    def ReadData(self):
        line_buffer = " "
        hdr_flag = False
        ml_value_flag = False #marks a multiline header
        offset = 0

        while True:
            offset = self.fid.tell()
            line_buffer = self.fid.readline()
           
            #remove leading and trailing whitespace symbols
            line_buffer = line_buffer.strip() 

            if line_buffer == "{" and not hdr_flag: #start with header
                hdr_flag = True                
                continue
            
            if hdr_flag:                 
                #stop reading when the end of the header is reached
                if line_buffer == "}": break  
                
                #continue if the line has no content
                if line_buffer == "": continue                

                #split key and value of the header entry      
                if not ml_value_flag:              
                    try:
                        [key,value] = edf_kv_split.split(line_buffer,1)
                    except:
                        print line_buffer
                    
                    key = key.strip()
                    value = value.strip()
                    
                    #if the value extends over multiple lines set the multiline value flag
                    if value[-1]!=";": 
                        ml_value_flag = True
                    else:
                        value = value[:-1]                         
                        value = value.strip()
                        self.header[key] = value                        
                else:
                    value = value + line_buffer
                    if value[-1]==";": 
                        ml_value_flag = False
                        
                        value = value[:-1]
                        value = value.strip()
                        self.header[key] = value
                
        #----------------start to read the data section----------------------

        #to read the data we have to open the file in binary mode
        binfid = open(self.full_filename,"rb")
        #evaluate some header entries
        fmt_str = DataTypeDict[self.header[self.dtkey]]
        #hdr_size = int(self.header["EDF_HeaderSize"])
        dimx = int(self.header[self.nxkey])
        dimy = int(self.header[self.nykey])

        #calculate the total number of pixles in the data block                                         
        tot_nofp = dimx*dimy 
        #move to the data section - jump over the header
        binfid.seek(offset,0)
        #read the data
        bindata = binfid.read(struct.calcsize(tot_nofp*fmt_str))
        num_data = struct.unpack(tot_nofp*fmt_str,bindata)
        
        #find the proper datatype
        if self.header[self.dtkey]=="SignedByte":
            self.data = numpy.array(num_data,dtype=numpy.int8)
        elif self.header[self.dtkey]=="SignedShort":
            self.data = numpy.array(num_data,dtype=numpy.int16)
        elif self.header[self.dtkey]=="SignedInteger":
            self.data = numpy.array(num_data,dtype=numpy.int32)
        elif self.header[self.dtkey]=="SignedLong":
            self.data = numpy.array(num_data,dtype=numpy.int64)
        elif self.header[self.dtkey]=="FloatValue":
            self.data = numpy.array(num_data,dtype=numpy.float)
        elif self.header[self.dtkey]=="DoubleValue":
            self.data = numpy.array(num_data,dtype=numpy.double)
        elif self.header[self.dtkey]=="UnsignedByte":
            self.data = numpy.array(num_data,dtype=numpy.uint8)
        elif self.header[self.dtkey]=="UnsignedShort":
            self.data = numpy.array(num_data,dtype=numpy.uint16)
        elif self.header[self.dtkey]=="UnsignedInt":
            self.data = numpy.array(num_data,dtype=numpy.uint32)
        elif self.header[self.dtkey]=="UnsignedLong":
            self.data = numpy.array(num_data,dtype=numpy.uint64)
        else:
            self.data = numpy.array(num_data,dtype=dtype.double)
            
        self.data = self.data.reshape(dimy,dimx)

        #close the binary file descriptor
        binfid.close()
        
        #return with file pointer to 0
        self.fid.seek(0)
        
    def Save2HDF5(self,h5,**keyargs):
        """
        Save2HDF5(h5,**keyargs):
        Saves the data stored in the EDF file in a HDF5 file as a HDF5 array.
        By default the data is stored in the root group of the HDF5 file - this 
        can be changed by passing the name of a target group or a path to the 
        target group via the "group" keyword argument.
        
        required arguments.
        h5 ................... a HDF5 file object
        
        optional keyword arguments:
        group ................ group where to store the data
        comp ................. activate compression - true by default
        """

        if keyargs.has_key("group"):
            if isinstance(keyargs["group"],str):
                g = h5.getNode(keyargs["group"])
            else:
                g = keyargs["group"]
        else:
            g = "/"
            
        if keyargs.has_key("comp"):
            compflag = keyargs["comp"]
        else:
            compflag = True
            
        #create the array name
        ca_name = os.path.split(self.filename)[-1]
        ca_name = os.path.splitext(ca_name)[0]
        if edf_name_start_num.match(ca_name):
            ca_name = "ccd_"+ca_name
        print ca_name
        ca_name = ca_name.replace(" ","_")
        
        #create the array description
        ca_desc = "EDF CCD data from file %s " %(self.filename)
            
        #create the Atom for the array
        a = tables.Atom.from_dtype(self.data.dtype)
        f = tables.Filters(complevel=7,complib="zlib",fletcher32=True)
        if compflag:
            ca = h5.createCArray(g,ca_name,a,self.data.shape,ca_desc,filters=f)
        else:
            ca = h5.createCArray(g,ca_name,a,self.data.shape,ca_desc,filters=f)
            
        #write the data
        ca[...] = self.data[...]
        
        #finally we have to append the attributes
        for k in self.header.keys():
            aname = k.replace(".","_")
            aname = aname.replace(" ","_")
            ca.attrs.__setattr__(aname,self.header[k])


    

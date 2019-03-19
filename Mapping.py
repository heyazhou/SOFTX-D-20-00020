#################################################################
#                                                               #
#          XRF MAP GENERATOR                                    #
#                        version: a1.4.2                        #
# @author: Sergio Lins               sergio.lins@roma3.infn.it  #
#################################################################

import sys
import numpy as np
import SpecMath
import SpecRead
import EnergyLib
from PyMca5.PyMcaMath import SpecArithmetic as Arithmetic
from PyMca5.PyMcaPhysics import Elements
import matplotlib.pyplot as plt
import time
import cv2
import math
import logging

logging.basicConfig(format = '%(asctime)s\t%(levelname)s\t%(message)s',
filename = 'process.log',level = logging.INFO)
f=open('process.log','w')
f.truncate(0)
logging.info('*'* 10 + ' MAPPING.PY LOG START ' + '*'* 10)
timer=time.time()
# FOR NOW THE STARTING SPECTRA MUST BE GIVEN MANUALLY IN SpecRead.py FILE
start = SpecRead.input

imagsize = SpecRead.getdimension()
imagex = imagsize[0]
imagey = imagsize[1]
dimension = imagex*imagey

def updateposition(a,b):
    currentx=a
    currenty=b
    if currenty == imagey-1:
#        print("We reached the end of the line, y= %d" % currenty)
        currenty=0
#        print("Now we reset the column, y= %d" % currenty)
        currentx+=1
#        print("And last we move to the next line, x= %d" % currentx)
    else:
        currenty+=1
#        print("We are still in the middle of the line, y+1 = %d" % currenty)
#    if currentx == imagex-1 and currenty == imagey-1:
#        print("END OF IMAGE")
    actual=([currentx,currenty])
    return actual

def plotdensitymap():
    currentspectra = start
    density_map = np.zeros([imagex,imagey])
    scan=([0,0])
    currentx=scan[0]
    currenty=scan[1]
    logging.info("Started acquisition of density map")
    for ITERATION in range(dimension):
        spec = currentspectra
#        print("Current X= %d\nCurrent Y= %d" % (currentx,currenty))
#        print("Current spectra is: %s" % spec)
        sum = SpecRead.getsum(spec)
        density_map[currentx][currenty]=sum          #_update matrix
        scan=updateposition(scan[0],scan[1])
        currentx=scan[0]
        currenty=scan[1]
        currentspectra = SpecRead.updatespectra(spec,dimension)
    logging.info("Finished fetching density map!")
    print("Execution took %s seconds" % (time.time() - timer))
    density_map = density_map.astype(np.float32)/density_map.max()
    density_map = 255*density_map
    image = colorize(density_map,'gray')
    plt.imshow(image, cmap='gray')
    plt.show()
    return image

def plotpeakmap(*args,ratio=None,plot=None,enhance=None):
    partialtimer = time.time()
    LocalElementList = args
    colorcode=['red','green','blue']
    eleenergy = EnergyLib.Energies
    logging.info(eleenergy)
    logging.info("Started energy axis calibration")
    energyaxis = SpecRead.calibrate(start,'file')
    logging.info("Finished energy axis calibration")
    stackimage = colorize(np.zeros([imagex,imagey]),'none')
    norm = normalize(energyaxis)
    for input in range(len(LocalElementList)):
        Element = LocalElementList[input]
        
        # STARTS IMAGE ACQUISITION FOR ELEMENT 'Element'
        
        if Element in Elements.ElementList:
            logging.info("Started acquisition of {0} map".format(Element))
            print("Fetching map image for %s..." % Element)
            pos = Elements.ElementList.index(Element)
            element = eleenergy[pos]*1000
            logging.warning("Energy {0} for element {1} being used as lookup!"\
                    .format(element,Element))
            currentspectra = start
            elmap = np.zeros([imagex,imagey])
            scan=([0,0])
            currentx=scan[0]
            currenty=scan[1]
            
            if ratio == True: 
                ratiofile = open('ratio.txt','w+')
                logging.warning("Ratio map will be generated!")
                kbindex = Elements.ElementList.index(Element) 
                kbenergy = EnergyLib.kbEnergies[kbindex]*1000
                logging.warning("Energy {0} for element {1} being used as lookup!"\
                        .format(kbenergy,Element))

            logging.info("Starting iteration over spectra...")
            for ITERATION in range(dimension):
                spec = currentspectra
#               print("Current X= %d\nCurrent Y= %d" % (currentx,currenty))
#               print("Current spectra is: %s" % spec)
                specdata = SpecRead.getdata(spec)
                sum = SpecMath.getpeakarea(element,specdata,energyaxis)
#                print("SUM={0}".format(sum))
                elmap[currentx][currenty] = sum
                
                if ratio == True:
                    ka = sum
                    kb = SpecMath.getpeakarea(kbenergy,specdata,energyaxis)
                    row = scan[0]
                    column = scan[1]
                    ratiofile.write("%d\t%d\t%d\t%d\n" % (row, column, ka, kb))

                scan = updateposition(scan[0],scan[1])
                currentx = scan[0]
                currenty = scan[1]
                currentspectra = SpecRead.updatespectra(spec,dimension)
            logging.info("Finished iteration process for element {}".format(Element))
            if ratio == True: ratiofile.close()
            
            logging.info("Started normalizing and coloring step")
            print("NORM={0}".format(norm))
            print("{0} MAX={1}".format(Element,elmap.max()))
            image = elmap/norm*255
            if enhance == True: image = elmap/elmap.max()*255
            image = colorize(image,colorcode[input])
            stackimage = cv2.addWeighted(image, 1, stackimage, 1, 0)
            logging.info("Finished normalizing and coloring step")
            print("Execution took %s seconds" % (time.time() - partialtimer))
            partialtimer = time.time()
    
    logging.info("Finished map acquisition!")
    
    if plot == True: 
        if enhance == True: 
            hist,bins = np.histogram(stackimage.flatten(),256,[0,256])
            cdf = hist.cumsum()
            cdf_norm = cdf * hist.max()/cdf.max()
            cdf_mask = np.ma.masked_equal(cdf,0)
            cdf_mask = (cdf_mask - cdf_mask.min())*255/(cdf_mask.max()-cdf_mask.min())
            cdf = np.ma.filled(cdf_mask,0).astype('uint8')
            stackimage = cdf[stackimage]
        plt.imshow(stackimage)
        plt.show()
    return stackimage

def normalize(energyaxis):
    MaxDetectedArea = 0
    currentspectra = start
    stackeddata = SpecMath.stacksum(start,dimension)
    stackedlist = stackeddata.tolist()
    absenergy = energyaxis[stackedlist.index(stackeddata.max())] * 1000
    print("ABSENERGY: {0}".format(absenergy))
    for iteration in range(dimension):
        spec = currentspectra
        specdata = SpecRead.getdata(spec)
        sum = SpecMath.getpeakarea(absenergy,specdata,energyaxis)
        if sum > MaxDetectedArea: MaxDetectedArea = sum
        currentspectra = SpecRead.updatespectra(spec,dimension)
    return MaxDetectedArea
        

def colorize(elementmap,color=None):
    R = np.zeros([imagex,imagey])
    G = np.zeros([imagex,imagey])
    B = np.zeros([imagex,imagey])
    A = np.zeros([imagex,imagey])
    elmap = elementmap
    pixel = []
    myimage = [[]]*(imagex-1)
    if color == 'red':
        R=R+elmap
        G=G+0
        B=B+0
        A=A+255
    elif color == 'green':
        R=R+0
        G=G+elmap
        B=B+0
        A=A+255
    elif color == 'blue':
        R=R+0
        G=G+0
        B=B+elmap
        A=A+255
    elif color == 'gray':
        R=R+elmap
        G=G+elmap
        B=B+elmap
        A=A+255
    for line in range(imagex-1):    
        for i in range(imagey-1):
            pixel.append(np.array([R[line][i],G[line][i],B[line][i],A[line][i]],dtype='float32'))
            myimage[line]=np.asarray(pixel,dtype='uint8')
        pixel = []
    image = np.asarray(myimage)
#    plt.imshow(myimage)
#    plt.show()
    return image

if __name__=="__main__":
    flag1 = sys.argv[1]
    if flag1 == '-help':
        print("USAGE: '-findelement x y'; plots a 2D map of elements 'x' and/or 'y'\n\
       '-plotmap'; plots a density map\n\
       '-plotstack'; plots the sum spectra of all sample. Optional: you can add '-semilog' to plot it in semilog mode.\n\
       '-getratios x'; creates the ka/kb or la/lb ratio image for element 'x'. K or L are chosen accordingly.")
    if flag1 == '-findelement':    
        if len(sys.argv) > 4: 
            raise Exception("More than 2 elements were selected! Try again with 2 or less inputs!")
            logging.exception("More than 2 elements were selected!")
        if len(sys.argv) > 2:
            element1 = None
            element2 = None
            if sys.argv[2] in Elements.ElementList:
                element1 = sys.argv[2]
            else: 
                raise Exception("%s not an element!" % sys.argv[2])
                logging.exception("{0} is not a chemical element!".format(sys.argv[2]))
            if len(sys.argv) > 3:
                if sys.argv[3] in Elements.ElementList:
                    element2 = sys.argv[3]
                else: 
                    if '-enhance' in sys.argv:
                        pass
                    else:
                        raise Exception("%s not an element!" % sys.argv[3])
                        logging.exception("{0} is not a chemical element!".format(sys.argv[3]))
            if '-enhance' in sys.argv:
                plotpeakmap(element1,element2,plot=True,enhance=True)
            else:
                plotpeakmap(element1,element2,plot=True)
        else: 
            raise Exception("No element input!")
            logging.exception("No element input!")
    if flag1 == '-plotmap':
        print("Fetching density map...")
        plotdensitymap()
    if flag1 == '-plotstack':
        if len(sys.argv) >= 3:
            flag2 = sys.argv[2]
        else:
            flag2 = None
        SpecRead.getstackplot(start,flag2)
    if flag1 == '-getratios':
        if len(sys.argv) > 3: raise Exception("More than one element selected!\nFor -getratios, please input only one element.")
        if len(sys.argv) > 2:
            element1 = None
            element2 = None
            if sys.argv[2] in Elements.ElementList:
                element1 = sys.argv[2]
            else: raise Exception("%s not an element!" % sys.argv[2])
            if len(sys.argv) > 3:
                if sys.argv[3] in Elements.ElementList:
                    element2 = sys.argv[3]
                else: raise Exception("%s not an element!" % sys.argv[3])
            plotpeakmap(element1,element2,ratio=True)
            ratiofile = 'ratio.txt'
            ratiomatrix = SpecRead.RatioMatrixReadFile(ratiofile)
            ratiomatrix = SpecRead.RatioMatrixTransform(ratiomatrix)
            #ratioimage = colorize(ratiomatrix,'gray')
            #cv2.addWeighted(ratioimage, 1, ratioimage, 0, 0)
            plt.imshow(ratiomatrix,cmap='gray')
            plt.show()
        else: raise Exception("No element input!")


"""
 Code for detection of Tachycardia/Bradycardia
 Created by CSIR-CEERI
 Dr. Madan Kumar Lakshmanan
 Version 2   
 Date - 01-January-2019

 Steps to capture and analyse PPG data
 -------------------------------------
 - Read Gearband data from INput Notepad file
 - Bin it to 10 seconds
 - Detrending, smoothing and filtering
 - Pulse Quality Index (PQI) measurement - Time & frequency domain metrics
 - Peak detection
 - Derivation of T.D. & F.D. HR/HRV measures
 - Feature set extraction - 3 minutes time duration with 10 seconds interval
 
"""
import numpy as np
from scipy.signal import savgol_filter,filtfilt,welch,butter
import seaborn as sns
from collections import Counter

# For colour prinitng of warning/error
# Madan, 8-Nov-2018
import sys
import math
from collections import Counter
import scipy as sc
from numpy import interp
import time
import peakutils
from itertools import islice
import xlwt




import matplotlib.pyplot as plt
plt.rcParams.update({'font.size': 20})

with open('filenames.txt') as f:
    lines = f.readlines()
lines=list(map(lambda x:x.strip('\n'),lines))
print(lines)
for filename in lines:
    
    sns.set(font_scale=12)
    sns.set_context("paper") #poster, talk,  paper



    decision_var=[]
    flag=[]
    book = xlwt.Workbook(encoding="utf-8")

    sheet1 = book.add_sheet("Sheet 1")
    sheet1.write(0, 0, "mHR")
    sheet1.write(0, 1, "stdHR")
    sheet1.write(0, 2, "cvHR")
    sheet1.write(0, 3, "RMSSD")
    sheet1.write(0, 4, "pNN20")
    sheet1.write(0, 5, "pNN30")
    sheet1.write(0, 6, "pNN40")
    sheet1.write(0, 7, "pNN50")
    sheet1.write(0, 8, "LFPower")
    sheet1.write(0, 9, "HFPower")
    sheet1.write(0, 10, "TPower")
    sheet1.write(0, 11, "LHRatio")
    sheet1.write(0, 12, "Shanon entropy")
    sheet1.write(0,13,"mPRH")
    sheet1.write(0,14,"instHR")
    sheet1.write(0,15,"Soft Decision")

    # Sampling frequency
    fs=25;

    #  FILTERS

    def butter_lowpass_filter(data, lowcut, fs, order=5):
        nyq = 0.5 * fs
        low = lowcut / nyq
        #high = highcut / nyq
        b, a = butter(order, [low], btype='low')
        y = filtfilt(b, a, data)
        return y


    #Data Conditioning
    data=[]
    smoothdata=[]
    filtereddata=[]
    data_trendRemoved=[]


    def popup(message, color):
        import tkinter as tk
        master = tk.Tk()
        msg = tk.Message(master, text = message)
        msg.config(bg=color, anchor='center', justify='center',aspect=480,font=('Arial', 9),relief='raised')

        w = 80 # width for the Tk root
        h = 50 # height for the Tk root

        # get screen width and height
        ws = master.winfo_screenwidth() # width of the screen
        hs = master.winfo_screenheight() # height of the screen

        # calculate x and y coordinates for the Tk root window
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)

        # set the dimensions of the screen 
        # and where it is placed
        master.geometry('%dx%d+%d+%d' % (w, h, x, y))

        #master.geometry('350x200')
        msg.pack()
        tk.mainloop()


    median_peak_rise=[]
    crests=[]
    troughs=[]
    peak_rise_height=[]
    def mprh(data):
        k=0
        while k<250:
            seg_data=data[k:k+25]    
            crest=np.max(data)
            trough=min(list(map(float,data)))
            peak_rise=np.subtract(crest,trough)
            peak_rise_height.append(peak_rise)
            k=k+25
        mprh=np.median(peak_rise_height)
        print('Median Peak-Rise Height:',mprh)
        return(mprh)
        

    def eta(data, unit='natural'):
                base = {
               'shannon' : 2.,
               'natural' : math.exp(1),
               'hartley' : 10.
                }

                if len(data) <= 1:
                   return 0

                counts = Counter()

                for d in data:
                    counts[d] += 1

                #print(counts)
                #print(counts.values())
                ent = 0

                probs = [float(c) / len(data) for c in counts.values()]
                #print(probs)
                for p in probs:
                    if p > 0.:
                       ent -= p * math.log(p, base[unit])
                       #print("Shannon Entropy: ",ent )
                return ent
        

    def hampel(x,k, t0=3):
        n = len(x)
        y = x #y is the corrected series
        L = 1.4826
        for i in range((k + 1),(n - k)):
            if np.isnan(x[(i - k):(i + k+1)]).all():
                continue
            x0 = np.nanmedian(x[(i - k):(i + k+1)])
            S0 = L * np.nanmedian(np.abs(x[(i - k):(i + k+1)] - x0))
            if (np.abs(x[i] - x0) > t0 * S0):
                y[i] = x0
        return(y)
        
    # Data Acquisition

    index = 0
    rr_peaks=[0]
    rr_Biglist=[]
    rr_interval=[]
    rr_interval_10secs=[]
    lastpeakfound=0
    flat_list=[]
    rr_BigDatalist=[]
    correctionFactor=0
    lastpeakfound=0
    bi=1

    durationWindow = 10 # 10 seconds data read for PQI
    fs=25 #samplig frequency of S3

    noFileRows =  2*durationWindow*fs  # Number of rows to be read
    #For example
    # I want to read 10s data
    # noFileRows = 2*10*25 #500 

    with open(filename) as myfile:
        first_to_fourthline = list(islice(myfile,noFileRows))
         #Ignore first to fourth lines
        first_to_fourthline = []

        print('*********************************************')
        print('COLLECTING 10-seconds SIGNAL CHUNKS')
        print('*********************************************')        
        
        while True:
            #time.sleep(10)
            head=list(islice(myfile,noFileRows))
            data=[]
            if not head:
                break
            #Data-cleaning
            for line in head:# because theres a /n in even places
                a = -1
                if index%2==0:
                    a=line.split(",")[1]
                index+=1
                if a != -1:
                    data=np.append(data,int(float(a)))
                    #print(a)
            #print(data)
            #Codefix - 4-July 2018
            ##print('The number of signal points read is:',len(data))
            if len(data) < noFileRows/2:
                break; #Break out of the while loop and store all the data

            # Signal Conditioning

            #Identify trends and remove it
            smoothdata=savgol_filter(data,101,4)
            data_trendRemoved=data-smoothdata

            # Filtering (3)
            lowcut = 4
            fs=25
            filtereddata = butter_lowpass_filter(data_trendRemoved, lowcut, fs, order=3)
           

            # FFT Computation
            #Set variables
            
            f, Pxx=welch(filtereddata, fs=25.0, window=('gaussian',len(filtereddata)), nfft=len(filtereddata))

            peaksValIndex = peakutils.indexes(Pxx)
            identifiedPeaks=Pxx[peaksValIndex]
            MaxPeakVal_Index = max(enumerate(Pxx), key=lambda x: x[1])[0]
       
            xdatanew=[f[xyz] for xyz in peaksValIndex]
            
            hr_fft=max(xdatanew)*60
   
           
            #plt.show()

            
            # PQI 1
            #if (len(peaksValIndex)<4 and (f[MaxPeakVal_Index] > 0.55 and f[MaxPeakVal_Index] < 2.5)): # Very restrictive
            
            if (len(peaksValIndex)<5 and (max(xdatanew) > 0.6 and max(xdatanew) < 2.5)): # 36 to 150 bpm
                print(" ")
            else:
                
                print("Error 1: Unhealthy Segment. Data Ignored \n")
                #Comment the line below when you don't want the figures
                
                continue
            

            # Peakdetection in PPG Signal

            #Minimum distance between pulses = at least half-a-pulse width
            MIN_PULSE_DIST = math.ceil(fs/2)
           
            indexes = peakutils.indexes(filtereddata,thres=0.5,min_dist=MIN_PULSE_DIST)
            ydatanew=[filtereddata[xyz] for xyz in indexes]

           
            data=[]
            
            #Expected number of pulses based on heart rate
            noPulsesExpected = math.floor(max(xdatanew)*durationWindow)
            noActualPulses = len(indexes)


            from peakutils.plot import plot as pplot 
            x=np.linspace(0,len(filtereddata)-1,len(filtereddata))
            plt.cla()
            plt.plot(x/fs, filtereddata)#, indexes)
            plt.xlabel('Time (in seconds)')
            plt.ylabel('Amplitude')
            plt.title('Signal Pulses')
            plt.pause(0.5)
    ##        
            
            
            # PQI 2
            
            if (noActualPulses < noPulsesExpected + 4) and (noActualPulses > noPulsesExpected - 4):  
                print(" ")
            else:
                print("Error 2: Unhealthy Segment. Data Ignored \n")
                
                
                continue


            #"""
            # RR Interval calculation for 10 seconds data
            for i in range (0, len(indexes)-1):
                    rr_interval_10secs.append(indexes[i+1] - indexes[i])

            BPM_inst = [(60*fs)/xy for xy in rr_interval_10secs]
            rr_interval_ms=np.multiply(rr_interval_10secs,(1000/fs))

            #Entropy calculation

            #Shannon Entropy & MPRH for A-Fib detection
            shE = eta (BPM_inst)
            print("sh ",shE)
            MPRH=mprh(filtereddata)
            median_peak_rise.append(MPRH)

                

            # Check for Tachycardia/Bradycardia over 10 sec signal segments
            instHr = np.array(BPM_inst)
            higherWhere = instHr >= 85
            lowerWhere = instHr < 60

            print('-------------------------------------------------------')
            print('Tachycardia/Bradycardia evaluated over 10-seconds')
            print('-------------------------------------------------------')
     
            highHowMany = len(instHr[higherWhere])
            lowHowMany = len(instHr[lowerWhere])

            print('Number of beats counted:',len(instHr))
            print('Number of instanteneous HR higher than 100:',highHowMany)
            print('Number of instanteneous HR lower than 60:',lowHowMany)

            if (shE>2.9):
                print("SOFT DECISION: POSSIBLE ATRIAL FIBRILLATION")
            elif (highHowMany >= 5):
                print("SOFT DECISION: POSSIBLE TACHYCARDIA\n")
            elif(lowHowMany >= 5):
                print("SOFT DECISION: POSSIBLE BRADYCARDIA\n")
            else:
                print("SOFT DECISION: NORMAL HEART-RATE \n")
                

   
            
            BPM_10secs = np.mean(BPM_inst);
    ##        print("Mean of BPM (10 seconds):{:8.2f}  ".format(BPM_10secs))
            stdHR_10secs = np.std(BPM_inst)
    ##        print("stdHR (10 seconds): {:8.2f} ".format(stdHR_10secs))

            rr_interval_10secs=[]    
           
            BPM_inst=[]
            stdHR_10secs=[]
            #Add correction factor
            rr_peak_locs=indexes+lastpeakfound+correctionFactor
            lastpeakfound=rr_peak_locs[-1]


            """
            Calculation of correction factor -> Number of Samples that constitute a Half-pulse
            Madan, 8-November 2018
            """
           
            ######################################################
          
            # Total number of samples in the time-window  of consideration = time-window*sampling frequency
            # Number of samples in the time-window of consideration = noActualPulses
            # Number of samples contained in 1 pulse = time-window*sampling frequency/noActualPulses
            # Number of samples in half-pulse = 1/2*(time-window*sampling frequency/noActualPulses)

            # Half Pulse width
            ######################################################
            correctionFactor = math.ceil((durationWindow*fs)/(noActualPulses*2))

           
            
            #The box which appends data as lists
            rr_Biglist.append(list(rr_peak_locs))

            
            rr_peak_locs=[]

            """
            Code to aggregate 6 bins data i.e 1 Mins of aggregated data
            """
            durationAggregateData = 1 # 1 minutes of aggregated data
            LIST_FILL_SIZE = (durationAggregateData*60)/durationWindow
            
            if len(rr_Biglist)%LIST_FILL_SIZE ==0:
                    
                #Process T.D., F.D., M.L.
                flat_list = np.hstack(rr_Biglist)          
                
                # RR Interval calculation for 1 minutes data
                for i in range (0, len(flat_list)-1):
                    rr_interval.append(flat_list[i+1] - flat_list[i])

                # OUTLIER DETECTION USING HAMPEL
               # rr_interval_hampel=hampel(rr_interval, k=5)
                #iBPM = [(60*fs)/xy for xy in rr_interval_hampel]

                iBPM = [(60*fs)/xy for xy in rr_interval]
                shE1 = eta (iBPM)
                print("sh ",shE1)
                
                

                    
                print('----------------------------------------------------------')
                print('Atrial Fibrillation/Tachycardia/Bradycardia evaluated over 1-min data')
                print('----------------------------------------------------------')

                instHr = np.array(iBPM)
                higherWhere = instHr >= 85
                lowerWhere = instHr < 60
                highHowMany = len(instHr[higherWhere])          
                lowHowMany = len(instHr[lowerWhere])

                print('Number of beats counted:',len(instHr))
                print('Number of instanteneous HR higher than 85:',highHowMany)
                print('Number of instanteneous HR lower than 60:',lowHowMany)

                soft_decision=''
                if (shE1>2.9):
                    print("Possible Atrial Fibrillation \n")
                    soft_decision='AF'
                    #popup('POSSIBLE ATRIAL FIBRILLATION', 'orange')
                    decision_var.append(1)  
                elif (len(instHr) >= 85):
                    print("SOFT DECISION: POSSIBLE TACHYCARDIA \n")
                    soft_decision='TACHYCARDIA'
                    #popup('POSSIBLE TACHYCARDIA', 'red')
                    decision_var.append(2)
            
                elif(len(instHr) <= 60):
                    print("SOFT DECISION: POSSIBLE BRADYCARDIA \n")
                    soft_decision='BRADYCARDIA'
                    #popup('POSSIBLE BRADYCARDIA', 'blue')
                    decision_var.append(3)
            
                else:
                    print("SOFT DECISION: NORMAL HEART-RATE \n ")
                    soft_decision='NORMAL'
                    #popup('NORMAL HEART-RATE', 'green')
                    decision_var.append(4)
            
                #for a-fib, tachy and brady
                #decision,num_most_common = Counter(decision_var).most_common(1)[0] 
                #print('-----------------------------------------------------------------------------')
                #print("Instantaneous Heart Rate values over 60 secs:",iBPM)
                print('-----------------------------------------------------------------------------')

                BPM = np.mean(iBPM);
  
                stdHR = np.std(iBPM)
   
                cvHR = BPM/stdHR
                cvHR = np.around(cvHR,3)
  

                #With outlier detection
                #rr_interval_ms=np.multiply(rr_interval_hampel,(1000/fs))
                rr_interval_ms=np.multiply(rr_interval,(1000/fs))
                #print("RRms : ",rr_interval_ms)
                
                rr_diff=[]
                for i in range (0, len(rr_interval_ms)-1):
                    rr_diff.append(rr_interval_ms[i+1] - rr_interval_ms[i])

                rmssd =np.sqrt(np.mean(np.square(rr_diff)))
                
                
                
                
   
            
                nn20 = [x for x in rr_diff if (x>20)]
                nn30 = [x for x in rr_diff if (x>30)]
                nn40 = [x for x in rr_diff if (x>40)] 
                nn50 = [x for x in rr_diff if (x>50)]
                pnn20 = float(len(nn20)) / float(len(rr_diff))
                pnn30 = float(len(nn30)) / float(len(rr_diff))
                pnn40 = float(len(nn40)) / float(len(rr_diff)) 
                pnn50 = float(len(nn50)) / float(len(rr_diff))
    

                RR_x = flat_list[1:] #Remove the first entry, because first interval is assigned to the second beat.
                RR_y = iBPM #Y-values are equal to interval lengths


                f_hr_s=4 # 4 Hz sampling rate
                #Create evenly spaced timeline starting at the second peak, its endpoint and length equal to position of last peak
                RR_x_new = np.linspace(RR_x[0],RR_x[-1],1000/f_hr_s)
                
                f = interp(RR_x_new, RR_x,RR_y) #Interpolate the signal with cubic spline interpolation
               # welch
                frq, Pxx1=welch(f, fs=5.0)
               

                lf = np.trapz(Pxx1[(frq>=0.04) & (frq<=0.15)])
                #Slice frequency spectrum where x is between 0.04 and 0.15Hz (LF), and use NumPy's trapezoidal integration function to find the area
            
                hf = np.trapz(Pxx1[(frq>=0.15) & (frq<=0.4)]) #Do the same for 0.16-0.5Hz (HF)
   

                tp= np.trapz(Pxx1[(frq>=0.04) & (frq<=0.4)])#Do the same for 0.16-0.5Hz (HF)
   
                lhratio=lf/hf
    
                sheet1.write(bi, 0, BPM)
                sheet1.write(bi, 1, stdHR)
                sheet1.write(bi, 2, cvHR)
                sheet1.write(bi, 3, rmssd)
                sheet1.write(bi, 4, pnn20)
                sheet1.write(bi, 5, pnn30)
                sheet1.write(bi, 6, pnn40)
                sheet1.write(bi, 7, pnn50)
                sheet1.write(bi, 8, lf)
                sheet1.write(bi, 9, hf)
                sheet1.write(bi, 10, tp)
                sheet1.write(bi, 11, lhratio)
                sheet1.write(bi, 12, shE1)
                sheet1.write(bi,13,MPRH)
                sheet1.write(bi,14,len(instHr))
                sheet1.write(bi,15,soft_decision)
                bi=bi+1

                
                
               
                
                """
                Housekeeping
                ------------
                Popping off the first bin
                """
                popped=rr_Biglist.pop(0)
                rr_interval=[]
                flat_list=[]
                iBPM=[]
                #plt.show()
                name='OUTPUT_METRICS/' + filename.strip("INPUT_PPGDATA")+ 'metrics.xls'
                book.save(name)
                
    decision_count=max(decision_var,key=decision_var.count)
    if decision_count==1:
        disease="Possible Atrial Fibrillation"
        print("Possible Atrial Fibrillation\n")
    elif decision_count==2:
        disease="Possible Tachycardia"
        print("Possible Tachycardia\n")
    elif decision_count==3:
        disease="Possible Bradycardia"
        print("Possible Bradycardia\n")
    else:
        disease= "Normal"
        print("Normal\n")
    popup(disease,"orange")
     
     

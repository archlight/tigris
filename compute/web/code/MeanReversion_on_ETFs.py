from zipline.api import order, record, symbol,symbols
import statsmodels.api as stat
import statsmodels.tsa.stattools as ts
from statsmodels.tsa.tsatools import lagmat, add_trend

import pandas as pd
import numpy as np

import pdb
# Put any initialization logic here.  The context object will be passed to
# the other methods in your algorithm.
def initialize(context):
    # set_symbol_lookup_date('2009-01-01')
    context.cost = 0.06  # (round trade cost) 0.03 per share
    context.secs = symbols('AAPL', 'GOOGL')
    context.drift = 0
    context.lag = 1
    context.c_val = 0.40  # critical level for ADF test
    
    # Money Management
    context.leverage_limit = 0.1
    
    # Set the no-trade-region
    context.dev_upper_threshold = 0.2
    context.dev_lower_threshold = 0.1
    
    context.freq = 5  # mins
    context.lookback = 100  # periods Note: 390 mins/6.5 hours per day
    context.trade_bars = 5  #
    context.freq_counter = 0  # Count the bars in tartget frequency, context.freq
    context.base_counter = 0  # Count the bars in base frequncy, 1m or 1d
    
    #  initialize the holders
    context.past_prices = {secs:[] for secs in context.secs}
    context.weights = []
    context.prices = []
    context.pct_allocation = []


# Will be called on every trade event for the securities you specify. 
def handle_data(context, data):
    # Record and plot the leverage of our portfolio over time. 
    record(leverage = context.account.leverage)
       
    context.base_counter += 1
    context.base_prices = add_prices(context, data)

    # 1. Add prices and determine the weight of stationary portfolio on X freq
    if context.freq_counter <= context.lookback:
        if context.base_counter % context.freq == 0:
            print 'Pre_trade freq_counter: %d' %context.freq_counter
            context.freq_counter += 1
            pct_allocation = pre_trade(context, data)
            if pct_allocation:
                context.pct_allocation = pct_allocation
            return
        else:
            return
               
    # 2. Trade using the weights trained earlier
    if (context.freq_counter >= context.lookback 
        and context.freq_counter < context.lookback + context.trade_bars):        
        if context.base_counter % context.freq == 0:
            print 'Go2_trade freq_counter: %d' %context.freq_counter
            context.freq_counter += 1
            pct_allocation = context.pct_allocation
        else:
            return
    else:
        context.freq_counter = context.lookback
        context.base_counter = 0
        return
    
    # Last check before placing order
    if pct_allocation is None:
        return
    
    # Place orders.
    print '-'*10, 'Trade'
    for stock, j in zip(data, range(0,len(data))):
        price = data[stock].price
        record(stock, price)
        print stock
        log.info(pct_allocation[j])
        order_target_percent(stock, pct_allocation[j])

''' Supplement function
    pre_trade: update the price and determine the percent allocation for trades later
    # Every X bars:
    # 1. Add the historical prices and update price matrix
    # 2. Calculate the weights for stationary portfolio
    # 3. Calculate the money allocation for the trades
 
'''
def pre_trade(context, data):
    # ------------------------------------------------------
    # Step 1. Add prices once every freq bars
    context.prices = add_prices(context, data)

    # ------------------------------------------------------
    # Step 2. Calcualte weights of staiontary portfolio
    
    if len(context.prices) < context.lookback: 
    # No further action if historical prices are not enough 
    # to perform stationary check
        return
    
    # update the weights of stationary portfolio
    # and retrive the OLS results from stationary test
    resOLS = coint_test(context, data)
    
    # ------------------------------------------------------
    # Step 3. Calculate the capital allocation
    if resOLS:
        pct_allocation = trade_allocation(context, data, resOLS)
        print 'weights calculated'
        # try:
        #     pct_allocation = trade_allocation(context, data, context.prices, context.weights)
        # except:
        #     pct_allocation = None
        return pct_allocation
    else:
        return None
    


def coint_test(context, data):
    # Calculate the weights to form the stationary portfolio
    
    # No further action if historical prices are not enough 
    # to perform stationary check
    if len(context.prices) >= context.lookback:    
        johansonResult = coint_johansen(context.prices, context.drift, context.lag)
        print 'np.mean(context.prices): %s' %str(np.mean(context.prices))
        # value = JohansonResult.eig
        context.weights = johansonResult.evec
        context.weights = context.weights[:,0]  # Use the first evec which has the highest eig
        context.weights  = context.weights/np.sum(np.abs(context.weights))
    else:
        context.weights = []
        
    TrainPort = []
    
    if context.weights is None:
        return None

    # Construct the stationary portfolio
    TrainPort = np.dot(context.prices, context.weights)
    TrainPort = np.asarray(TrainPort)
    TrainPort = TrainPort[0,:]
    context.TrainPort = TrainPort
    
    # Use adf test to retrive the OLS model
    adfstat, pvalue, critvalues, resstore = ts.adfuller(TrainPort, maxlag=context.lag, 
                                                        regression="c", autolag=None, 
                                                        store=True, regresults=True)
    
    # skip to next bar if the stationary of current model is not significant
    if pvalue > context.c_val:
        # print 'The p value of adf test for constructed portfolio: %f' %pvalue
        return None
    else:
        return resstore.resols
         

def trade_allocation(context, data, resOLS):
    
    olsPara = resOLS.params  # OLS paramters for [x, dx, 1]
    resid = resOLS.resid
    ols_var = np.dot(resid, np.transpose(resid))/(resOLS.df_resid)
    
    # Replicate the OLS in adf test to predict the movement of stationary portfolio
    # RecentData = TrainPort[-context.lookback/50:]  #  only the recent data matters
    RecentData = context.TrainPort
    xdiff = np.diff(RecentData)
    nobs = xdiff.shape[0]
    xdall = np.column_stack((RecentData[-nobs:], xdiff[:,None])) 
    x = add_trend(xdall[:,:context.lag+1], 'c')
    y_pred = np.dot(x, olsPara)
    y_actual = xdiff[-nobs:]
        
    profit_potential = y_pred[-1]/context.cost
    # y_mean = np.mean(TrainPort)
    # y_std = np.std(TrainPort)

    # Calculate the score of deviation from current value
    # dev_score = y_pred[-1]#/np.sqrt(ols_var)
    # dev_score = -(y_pred[-1] - y_mean)/y_std
    # dev_score = -(TrainPort[-1] - np.mean(TrainPort))/np.std(TrainPort)
    
    curr_price = context.base_prices[-1,:]
    dollar_allocation = np.multiply(curr_price, context.weights)*profit_potential
    pct_allocation = context.leverage_limit*dollar_allocation/np.sum(np.abs(dollar_allocation))
    pct_allocation = np.asarray(pct_allocation)
    pct_allocation = pct_allocation[0,:]
    
    # print '-'*20
    # print 'ADF test statistics: %f' %adfstat
    # print 'ADF test critvalues: %s' %str(critvalues)
    # print 'ADF pvalue: %f' %pvalue
    # print ' '
    # print dir(resOLS)
    # print 'Predic value: %s' %str(y_pred[-5:])
    # print 'Fitted value: %s' %str(resOLS.fittedvalues[-5:])
    # print 'Actual value: %s' %str(y_actual[-5:])
    # print ' '
    # print 'Latest value of TrainPort: %f' %TrainPort[-1]
    # print 'Mean value of TrainPort: %f' %np.mean(TrainPort)
    # print 'Std Value of TrainPort: %f' %np.std(TrainPort)
    # print ' '
    # print 'avg of actual change: %f' %np.mean(abs(y_actual))
    # print 'std of actual change: %f' %np.std(y_actual)
    # print ' '
    # print 'avg of pred change: %f' %np.mean(abs(y_pred))
    # print 'std of pred change: %f' %np.std(y_pred)
    # print ' '
    # print 'The predicted bar: %f' %y_pred[-1]
    # print 'The current bar: %f' %y_actual[-1]
    # print ' '
    # print 'The ols std: %f' %np.sqrt(ols_var)
    # print 'mse_total %f' %resOLS.mse_total
    # print 'OLS rsquared: %f' %resOLS.rsquared
    # print 'profit_potential: %f' %profit_potential
    # print 'dev_score: %f' %dev_score
    
    # print 'Dollar Allocation: %s' %str(dollar_allocation)
    # if abs(y_pred[-1]) > 2*context.cost/abs(TrainPort[-1]):
    #     return pct_allocation
    # elif abs(y_pred[-1]) < context.cost/abs(TrainPort[-1]):
    #     return pct_allocation*0
    # else:
    #     return None
    
    # Trading window is determined by the abs(dev_score)
    if abs(profit_potential) < context.dev_lower_threshold:
        # Liquidate all positions if fall below lower threshold
        return pct_allocation*0.
    elif abs(profit_potential) < context.dev_upper_threshold:
        # Do nothing
        return None
    else:
        # Rebalance if the dev is above the upper threshold.
        return pct_allocation
'''
    SUPPLEMENTAL METHOD 1:
    add_prices(context, data) - Adds all prices on a rolling basis
'''

# Adds prices on a rolling basis
def add_prices(context, data):
    
    if data is None:
        return
    
    for secs in data:
        context.past_prices[secs].append(data[secs].price)
        if len(context.past_prices[secs]) > context.lookback:
            del context.past_prices[secs][0]
            
    prices = np.column_stack((context.past_prices[sec] for sec in data))
    prices = np.asmatrix(prices)
    return prices
            
'''
function result = johansen(x,p,k)
% PURPOSE: perform Johansen cointegration tests
% -------------------------------------------------------
% USAGE: result = johansen(x,p,k)
% where:      x = input matrix of time-series in levels, (nobs x m)
%             p = order of time polynomial in the null-hypothesis
%                 p = -1, no deterministic part
%                 p =  0, for constant term
%                 p =  1, for constant plus time-trend
%                 p >  1, for higher order polynomial
%             k = number of lagged difference terms used when
%                 computing the estimator
% -------------------------------------------------------
% RETURNS: a results structure:
%          result.eig  = eigenvalues  (m x 1)
%          result.evec = eigenvectors (m x m), where first
%                        r columns are normalized coint vectors
%          result.lr1  = likelihood ratio trace statistic for r=0 to m-1
%                        (m x 1) vector
%          result.lr2  = maximum eigenvalue statistic for r=0 to m-1
%                        (m x 1) vector
%          result.cvt  = critical values for trace statistic
%                        (m x 3) vector [90% 95% 99%]
%          result.cvm  = critical values for max eigen value statistic
%                        (m x 3) vector [90% 95% 99%]
%          result.ind  = index of co-integrating variables ordered by
%                        size of the eigenvalues from large to small
% -------------------------------------------------------
% NOTE: c_sja(), c_sjt() provide critical values generated using
%       a method of MacKinnon (1994, 1996).
%       critical values are available for n<=12 and -1 <= p <= 1,
%       zeros are returned for other cases.
% -------------------------------------------------------
% SEE ALSO: prt_coint, a function that prints results
% -------------------------------------------------------
% References: Johansen (1988), 'Statistical Analysis of Co-integration
% vectors', Journal of Economic Dynamics and Control, 12, pp. 231-254.
% MacKinnon, Haug, Michelis (1996) 'Numerical distribution
% functions of likelihood ratio tests for cointegration',
% Queen's University Institute for Economic Research Discussion paper.
% (see also: MacKinnon's JBES 1994 article
% -------------------------------------------------------

% written by:
% James P. LeSage, Dept of Economics
% University of Toledo
% 2801 W. Bancroft St,
% Toledo, OH 43606
% jlesage@spatial-econometrics.com

% ****************************************************************
% NOTE: Adina Enache provided some bug fixes and corrections that
%       she notes below in comments. 4/10/2000
% ****************************************************************
'''
# import numpy as np
from numpy import zeros, ones, flipud, log
from numpy.linalg import inv, eig, cholesky as chol
from statsmodels.regression.linear_model import OLS

# from coint_tables import c_sja, c_sjt

tdiff = np.diff

class Holder(object):
    pass

def rows(x):
    return x.shape[0]

def trimr(x, front, end):
    if end > 0:
        return x[front:-end]
    else:
        return x[front:]

import statsmodels.tsa.tsatools as tsat
mlag = tsat.lagmat

def mlag_(x, maxlag):
    '''return all lags up to maxlag
    '''
    return x[:-lag]

def lag(x, lag):
    return x[:-lag]

def detrend(y, order):
    if order == -1:
        return y
    return OLS(y, np.vander(np.linspace(-1,1,len(y)), order+1)).fit().resid

def resid(y, x):
    if x.size == 0:
        return y
    r = y - np.dot(x, np.dot(np.linalg.pinv(x), y))
    return r




def coint_johansen(x, p, k, coint_trend=None):

    #    % error checking on inputs
    #    if (nargin ~= 3)
    #     error('Wrong # of inputs to johansen')
    #    end
    nobs, m = x.shape

    #why this?  f is detrend transformed series, p is detrend data
    if (p > -1):
        f = 0
    else:
        f = p

    if coint_trend is not None:
        f = coint_trend  #matlab has separate options

    x     = detrend(x,p)
    dx    = tdiff(x,1, axis=0)
    #dx    = trimr(dx,1,0)
    z     = mlag(dx,k)#[k-1:]
    # print z.shape
    z = trimr(z,k,0)
    z     = detrend(z,f)
    # print dx.shape
    dx = trimr(dx,k,0)

    dx    = detrend(dx,f)
    #r0t   = dx - z*(z\dx)
    r0t   = resid(dx, z)  #diff on lagged diffs
    #lx = trimr(lag(x,k),k,0)
    lx = lag(x,k)
    lx = trimr(lx, 1, 0)
    dx    = detrend(lx,f)
    # print 'rkt', dx.shape, z.shape
    #rkt   = dx - z*(z\dx)
    rkt   = resid(dx, z)  #level on lagged diffs
    skk   = np.dot(rkt.T, rkt) / rows(rkt)
    sk0   = np.dot(rkt.T, r0t) / rows(rkt)
    s00   = np.dot(r0t.T, r0t) / rows(r0t)
    sig   = np.dot(sk0, np.dot(inv(s00), (sk0.T)))
    tmp   = inv(skk)
    #du, au = eig(np.dot(tmp, sig))
    au, du = eig(np.dot(tmp, sig))  #au is eval, du is evec
    #orig = np.dot(tmp, sig)

    #% Normalize the eigen vectors such that (du'skk*du) = I
    temp   = inv(chol(np.dot(du.T, np.dot(skk, du))))
    dt     = np.dot(du, temp)


    #JP: the next part can be done much  easier

    #%      NOTE: At this point, the eigenvectors are aligned by column. To
    #%            physically move the column elements using the MATLAB sort,
    #%            take the transpose to put the eigenvectors across the row

    #dt = transpose(dt)

    #% sort eigenvalues and vectors

    #au, auind = np.sort(diag(au))
    auind = np.argsort(au)
    #a = flipud(au)
    aind = flipud(auind)
    a = au[aind]
    #d = dt[aind,:]
    d = dt[:,aind]

    #%NOTE: The eigenvectors have been sorted by row based on auind and moved to array "d".
    #%      Put the eigenvectors back in column format after the sort by taking the
    #%      transpose of "d". Since the eigenvectors have been physically moved, there is
    #%      no need for aind at all. To preserve existing programming, aind is reset back to
    #%      1, 2, 3, ....

    #d  =  transpose(d)
    #test = np.dot(transpose(d), np.dot(skk, d))

    #%EXPLANATION:  The MATLAB sort function sorts from low to high. The flip realigns
    #%auind to go from the largest to the smallest eigenvalue (now aind). The original procedure
    #%physically moved the rows of dt (to d) based on the alignment in aind and then used
    #%aind as a column index to address the eigenvectors from high to low. This is a double
    #%sort. If you wanted to extract the eigenvector corresponding to the largest eigenvalue by,
    #%using aind as a reference, you would get the correct eigenvector, but with sorted
    #%coefficients and, therefore, any follow-on calculation would seem to be in error.
    #%If alternative programming methods are used to evaluate the eigenvalues, e.g. Frame method
    #%followed by a root extraction on the characteristic equation, then the roots can be
    #%quickly sorted. One by one, the corresponding eigenvectors can be generated. The resultant
    #%array can be operated on using the Cholesky transformation, which enables a unit
    #%diagonalization of skk. But nowhere along the way are the coefficients within the
    #%eigenvector array ever changed. The final value of the "beta" array using either method
    #%should be the same.


    #% Compute the trace and max eigenvalue statistics */
    lr1 = zeros(m)
    lr2 = zeros(m)
    cvm = zeros((m,3))
    cvt = zeros((m,3))
    iota = ones(m)
    t, junk = rkt.shape
    for i in range(0, m):
        tmp = trimr(np.log(iota-a), i ,0)
        lr1[i] = -t * np.sum(tmp, 0)  #columnsum ?
        #tmp = np.log(1-a)
        #lr1[i] = -t * np.sum(tmp[i:])
        lr2[i] = -t * np.log(1-a[i])
        cvm[i,:] = c_sja(m-i,p)
        cvt[i,:] = c_sjt(m-i,p)
        aind[i]  = i
    #end

    result = Holder()
    #% set up results structure
    #estimation results, residuals
    result.rkt = rkt
    result.r0t = r0t
    result.eig = a
    result.evec = d  #transposed compared to matlab ?
    result.lr1 = lr1
    result.lr2 = lr2
    result.cvt = cvt
    result.cvm = cvm
    result.ind = aind
    result.meth = 'johansen'

    return result

# -*- coding: utf-8 -*-
"""

Created on Thu Aug 30 12:26:38 2012

Author: Josef Perktold
"""
'''
function jc =  c_sja(n,p)
% PURPOSE: find critical values for Johansen maximum eigenvalue statistic
% ------------------------------------------------------------
% USAGE:  jc = c_sja(n,p)
% where:    n = dimension of the VAR system
%           p = order of time polynomial in the null-hypothesis
%                 p = -1, no deterministic part
%                 p =  0, for constant term
%                 p =  1, for constant plus time-trend
%                 p >  1  returns no critical values
% ------------------------------------------------------------
% RETURNS: a (3x1) vector of percentiles for the maximum eigenvalue
%          statistic for: [90% 95% 99%]
% ------------------------------------------------------------
% NOTES: for n > 12, the function returns a (3x1) vector of zeros.
%        The values returned by the function were generated using
%        a method described in MacKinnon (1996), using his FORTRAN
%        program johdist.f
% ------------------------------------------------------------
% SEE ALSO: johansen()
% ------------------------------------------------------------
% References: MacKinnon, Haug, Michelis (1996) 'Numerical distribution
% functions of likelihood ratio tests for cointegration',
% Queen's University Institute for Economic Research Discussion paper.
% -------------------------------------------------------

% written by:
% James P. LeSage, Dept of Economics
% University of Toledo
% 2801 W. Bancroft St,
% Toledo, OH 43606
% jlesage@spatial-econometrics.com
'''

ss_ejcp0 = '''\
         2.9762  4.1296  6.9406
         9.4748 11.2246 15.0923
        15.7175 17.7961 22.2519
        21.8370 24.1592 29.0609
        27.9160 30.4428 35.7359
        33.9271 36.6301 42.2333
        39.9085 42.7679 48.6606
        45.8930 48.8795 55.0335
        51.8528 54.9629 61.3449
        57.7954 61.0404 67.6415
        63.7248 67.0756 73.8856
        69.6513 73.0946 80.0937'''

ss_ejcp1 = '''\
         2.7055   3.8415   6.6349
        12.2971  14.2639  18.5200
        18.8928  21.1314  25.8650
        25.1236  27.5858  32.7172
        31.2379  33.8777  39.3693
        37.2786  40.0763  45.8662
        43.2947  46.2299  52.3069
        49.2855  52.3622  58.6634
        55.2412  58.4332  64.9960
        61.2041  64.5040  71.2525
        67.1307  70.5392  77.4877
        73.0563  76.5734  83.7105'''

ss_ejcp2 = '''\
         2.7055   3.8415   6.6349
        15.0006  17.1481  21.7465
        21.8731  24.2522  29.2631
        28.2398  30.8151  36.1930
        34.4202  37.1646  42.8612
        40.5244  43.4183  49.4095
        46.5583  49.5875  55.8171
        52.5858  55.7302  62.1741
        58.5316  61.8051  68.5030
        64.5292  67.9040  74.7434
        70.4630  73.9355  81.0678
        76.4081  79.9878  87.2395'''

ejcp0 = np.array(ss_ejcp0.split(),float).reshape(-1,3)
ejcp1 = np.array(ss_ejcp1.split(),float).reshape(-1,3)
ejcp2 = np.array(ss_ejcp2.split(),float).reshape(-1,3)

def c_sja(n, p):
    if ((p > 1) or (p < -1)):
        jc = np.zeros(3)
    elif ((n > 12) or (n < 1)):
        jc = np.zeros(3)
    elif p == -1:
        jc = ejcp0[n-1,:]
    elif p == 0:
        jc = ejcp1[n-1,:]
    elif p == 1:
        jc = ejcp2[n-1,:]

    return jc

'''
function jc = c_sjt(n,p)
% PURPOSE: find critical values for Johansen trace statistic
% ------------------------------------------------------------
% USAGE:  jc = c_sjt(n,p)
% where:    n = dimension of the VAR system
%               NOTE: routine doesn't work for n > 12
%           p = order of time polynomial in the null-hypothesis
%                 p = -1, no deterministic part
%                 p =  0, for constant term
%                 p =  1, for constant plus time-trend
%                 p >  1  returns no critical values
% ------------------------------------------------------------
% RETURNS: a (3x1) vector of percentiles for the trace
%          statistic for [90% 95% 99%]
% ------------------------------------------------------------
% NOTES: for n > 12, the function returns a (3x1) vector of zeros.
%        The values returned by the function were generated using
%        a method described in MacKinnon (1996), using his FORTRAN
%        program johdist.f
% ------------------------------------------------------------
% SEE ALSO: johansen()
% ------------------------------------------------------------
% % References: MacKinnon, Haug, Michelis (1996) 'Numerical distribution
% functions of likelihood ratio tests for cointegration',
% Queen's University Institute for Economic Research Discussion paper.
% -------------------------------------------------------

% written by:
% James P. LeSage, Dept of Economics
% University of Toledo
% 2801 W. Bancroft St,
% Toledo, OH 43606
% jlesage@spatial-econometrics.com

% these are the values from Johansen's 1995 book
% for comparison to the MacKinnon values
%jcp0 = [ 2.98   4.14   7.02
%        10.35  12.21  16.16
%        21.58  24.08  29.19
%        36.58  39.71  46.00
%        55.54  59.24  66.71
%        78.30  86.36  91.12
%       104.93 109.93 119.58
%       135.16 140.74 151.70
%       169.30 175.47 187.82
%       207.21 214.07 226.95
%       248.77 256.23 270.47
%       293.83 301.95 318.14];
%
'''


ss_tjcp0 = '''\
         2.9762   4.1296   6.9406
        10.4741  12.3212  16.3640
        21.7781  24.2761  29.5147
        37.0339  40.1749  46.5716
        56.2839  60.0627  67.6367
        79.5329  83.9383  92.7136
       106.7351 111.7797 121.7375
       137.9954 143.6691 154.7977
       173.2292 179.5199 191.8122
       212.4721 219.4051 232.8291
       255.6732 263.2603 277.9962
       302.9054 311.1288 326.9716'''


ss_tjcp1 = '''\
          2.7055   3.8415   6.6349
         13.4294  15.4943  19.9349
         27.0669  29.7961  35.4628
         44.4929  47.8545  54.6815
         65.8202  69.8189  77.8202
         91.1090  95.7542 104.9637
        120.3673 125.6185 135.9825
        153.6341 159.5290 171.0905
        190.8714 197.3772 210.0366
        232.1030 239.2468 253.2526
        277.3740 285.1402 300.2821
        326.5354 334.9795 351.2150'''

ss_tjcp2 = '''\
           2.7055   3.8415   6.6349
          16.1619  18.3985  23.1485
          32.0645  35.0116  41.0815
          51.6492  55.2459  62.5202
          75.1027  79.3422  87.7748
         102.4674 107.3429 116.9829
         133.7852 139.2780 150.0778
         169.0618 175.1584 187.1891
         208.3582 215.1268 228.2226
         251.6293 259.0267 273.3838
         298.8836 306.8988 322.4264
         350.1125 358.7190 375.3203'''

tjcp0 = np.array(ss_tjcp0.split(),float).reshape(-1,3)
tjcp1 = np.array(ss_tjcp1.split(),float).reshape(-1,3)
tjcp2 = np.array(ss_tjcp2.split(),float).reshape(-1,3)

def c_sjt(n, p):
    if ((p > 1) or (p < -1)):
        jc = np.zeros(3)
    elif ((n > 12) or (n < 1)):
        jc = np.zeros(3)
    elif p == -1:
        jc = tjcp0[n-1,:]
    elif p == 0:
        jc = tjcp1[n-1,:]
    elif p == 1:
        jc = tjcp2[n-1,:]
    else:
        raise ValueError('invalid p')

    return jc

if __name__ == '__main__':
    for p in range(-2, 3, 1):
        for n in range(12):
            print n, p
            print c_sja(n, p)
            print c_sjt(n, p)

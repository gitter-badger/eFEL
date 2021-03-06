"""eFEL Python API functions.

This module provides the user-facing Python API of the eFEL. 
The convenience functions defined here call the underlying 'cppcore' library
to hide the lower level API from the user.
All functions in this module can be called as efel.functionname, it is 
not necessary to include 'api' as in efel.api.functionname.
"""

"""
Copyright (c) 2015, EPFL/Blue Brain Project

 This file is part of eFEL <https://github.com/BlueBrain/eFEL>

 This library is free software; you can redistribute it and/or modify it under
 the terms of the GNU Lesser General Public License version 3.0 as published
 by the Free Software Foundation.

 This library is distributed in the hope that it will be useful, but WITHOUT
 ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
 details.

 You should have received a copy of the GNU Lesser General Public License
 along with this library; if not, write to the Free Software Foundation, Inc.,
 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""

# pylint: disable=W0602,W0603,W0702, F0401, W0612, R0912

import numpy
import os

import efel
import efel.cppcore as cppcore

_settings = efel.Settings()


def setDependencyFileLocation(location):
    """Set the location of the Dependency file
    
    The eFEL uses 'Dependency' files to let the user define which versions
    of certain features are used to calculate.
    The installation directory of the eFEL contains a default 
    'DependencyV5.txt' file. Unless the user wants to change this file, 
    it is not necessary to call this function.

    Parameters
    ==========
    location : string
               path to the location of a Dependency file    
    """

    global dependencyFileLocation
    if not os.path.exists(location):
        raise Exception(
            "Path to dependency file {%s} doesn't exist" %
            location)
    _settings.dependencyfile_path = location


def getDependencyFileLocation():
    """Get the location of the Dependency file
    
    The eFEL uses 'Dependency' files to let the user define which versions
    of certain features are used to calculate.
    The installation directory of the eFEL contains a default 
    'DependencyV5.txt' file.

    Returns
    =======
    location : string
               path to the location of a Dependency file
    """

    return _settings.dependencyfile_path


def setThreshold(newThreshold):
    """Set the spike detection threshold in the eFEL
    
    Parameters
    ==========
    threshold : float
                The new spike detection threshold value (in the same units
                as the traces, e.g. mV).
    """
    _settings.threshold = newThreshold


def setDerivativeThreshold(newDerivativeThreshold):
    """Set the threshold for the derivate for detecting the spike onset
    
    Some feature us a threshold on dV/dt to calculate the beginning of an
    action potential. This function allows you to set this threshold.

    Parameters
    ==========
    derivative_threshold : float
                The new derivative threshold value (in the same units
                as the traces, e.g. mV/ms).
    """
    _settings.derivate_threshold = newDerivativeThreshold


def getFeatureNames():
    """Return a list with the name of all the available features
    
    Returns
    =======
    feature_names : list of strings
                    A list that contains all the feature names available in
                    the eFEL. These names can be used in the featureNames
                    argument of e.g. getFeatureValues()
    """

    cppcore.Initialize(_settings.dependencyfile_path, "log")
    feature_names = []
    cppcore.getFeatureNames(feature_names)

    return feature_names


def getFeatureValues(traces, featureNames):
    """Calculate feature values for a list of traces.

    This function is the core of the eFEL API. A list of traces (in the form
    of dictionaries) is passed as argument, together with a list of feature
    names. 

    The return value consists of a list of dictionaries, one for each input
    trace. The keys in the dictionaries are the names of the calculated 
    features, the corresponding values are lists with the feature values.
    Beware that every feature returns an array of values. E.g. AP_amplitude
    will return a list with the amplitude of every action potential.

    Parameters
    ==========
    traces : list of trace dicts
             Every trace dict represent one trace. The dict should have the
             following keys: 'T', 'V', 'stim_start', 'stim_end'
    feature_names : list of string
                  List with the names of the features to be calculated on all
                  the traces.
    Returns
    =======
    feature_values : list of dicts
                     For every input trace a feature value dict is return (in
                     the same order). The dict contains the keys of
                     'feature_names', every key contains a numpy array with
                     the feature values returned by the C++ efel code.
                     The value is None if an error occured during the 
                     calculation of the feature.
    """
    featureDicts = []

    for trace in traces:
        featureDict = {}

        if 'stim_start' in trace and 'stim_end' in trace:
            if len(trace['stim_start']) == 1 and len(trace['stim_end']) == 1:
                if trace['stim_end'][0] <= trace['stim_start'][0]:
                    raise Exception(
                        'stim_end needs to be larger than '
                        'stim_start:\nstim_start=%f stim_end=%f' %
                        (trace['stim_start'][0], trace['stim_end'][0]))
            else:
                raise Exception('stim_start and stim_end in the trace '
                                'dictionary need to be lists of 1 element')

        else:
            raise Exception('stim_start or stim_end missing from trace')

        cppcore.Initialize(_settings.dependencyfile_path, "log")

        # First set some settings that are used by the feature extraction
        cppcore.setFeatureDouble('spike_skipf', [0.1])
        cppcore.setFeatureInt('max_spike_skip', [2])
        cppcore.setFeatureDouble('Threshold',
                                 [_settings.threshold])
        cppcore.setFeatureDouble('DerivativeThreshold',
                                 [_settings.derivative_threshold])
        cppcore.setFeatureDouble('interp_step', [0.1])
        cppcore.setFeatureDouble('burst_factor', [1.5])
        cppcore.setFeatureDouble("initial_perc", [0.1])

        # Next set time, voltage and the stimulus start and end
        for item in trace.keys():
            cppcore.setFeatureDouble(item, [x for x in trace[item]])

        for featureName in featureNames:
            featureType = cppcore.featuretype(featureName)
            if featureType == "double":
                cppcoreFeatureValues = list()
                try:
                    exitCode = cppcore.getFeatureDouble(
                        featureName,
                        cppcoreFeatureValues)
                except:
                    exitCode = -1
            elif featureType == "int":
                cppcoreFeatureValues = list()
                exitCode = cppcore.getFeatureInt(
                    featureName,
                    cppcoreFeatureValues)
            else:
                print "Feature %s has an unknown type: %s" % \
                    (featureName, featureType)
                exit(1)
            if exitCode < 0:
                import warnings
                warnings.warn(
                    "Error while calculating feature %s: %s" %
                    (featureName, cppcore.getgError()),
                    RuntimeWarning)
                featureDict[featureName] = None
            else:
                featureDict[featureName] = numpy.array(cppcoreFeatureValues)

        featureDicts.append(featureDict)
    return featureDicts


def getMeanFeatureValues(traces, featureNames):
    """Convenience function that returns the mean values from getFeatureValues().

    Instead of return a list of values for every feature as getFeatureValues()
    does, this function returns per trace one value for every feature, namely 
    the mean value.

    Parameters
    ==========
    traces : list of trace dicts
             Every trace dict represent one trace. The dict should have the
             following keys: 'T', 'V', 'stim_start', 'stim_end'
    feature_names : list of string
                    List with the names of the features to be calculated on all
                    the traces.
    Returns
    =======
    feature_values : list of dicts
                     For every input trace a feature value dict is return (in
                     the same order). The dict contains the keys of
                     'feature_names', every key contains the mean of the array
                     that is returned by getFeatureValues()
                     The value is None if an error occured during the 
                     calculation of the feature, or if the feature value array
                     was empty.
    """

    featureDicts = getFeatureValues(traces, featureNames)
    for featureDict in featureDicts:
        for (key, values) in featureDict.items():
            if values is None or len(values) == 0:
                featureDict[key] = None
            else:
                featureDict[key] = numpy.mean(values)

    return featureDicts

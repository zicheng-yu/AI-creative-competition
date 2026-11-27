"""Shared server-bank retention model for planning costs and settled energy."""
import numpy as np
from scipy.ndimage import maximum_filter1d

from .world import KEEPALIVE


def powered_banks(required, capacity):
    """Keep idle banks powered, cancelling outstanding holds when capacity is lost."""
    if len(capacity)==1 or np.all(capacity==capacity[0]):
        held = maximum_filter1d(required,size=KEEPALIVE+1,axis=0,
                                origin=KEEPALIVE//2,mode="constant",cval=0.)
        return np.minimum(capacity,held)
    online = np.minimum(required,capacity)
    for lag in range(1,min(KEEPALIVE+1,len(capacity))):
        held = required[:-lag]
        for offset in range(1,lag+1):
            held = np.minimum(held,capacity[offset:len(capacity)-lag+offset])
        online[lag:] = np.maximum(online[lag:],held)
    return online

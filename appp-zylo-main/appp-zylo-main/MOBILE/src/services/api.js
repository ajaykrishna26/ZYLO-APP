import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Config from '../config';

// Create axios instance with optimized configuration
const api = axios.create({
    baseURL: Config.API_BASE_URL,
    timeout: Config.REQUEST_TIMEOUT,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Track if refresh is in progress to avoid multiple refresh requests
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve(token);
        }
    });
    
    isRefreshing = false;
    failedQueue = [];
};

// Retry logic for failed requests
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // Start with 1 second

const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const retryRequest = async (config, retryCount = 0) => {
    try {
        return await api.request(config);
    } catch (error) {
        // Retry on network errors or 5xx errors (but not 401)
        if (retryCount < MAX_RETRIES && 
            (error.code === 'ECONNABORTED' || 
             error.code === 'ENOTFOUND' ||
             (error.response?.status >= 500 && error.response?.status !== 401))) {
            
            const waitTime = RETRY_DELAY * Math.pow(2, retryCount);
            await delay(waitTime);
            return retryRequest(config, retryCount + 1);
        }
        throw error;
    }
};

// Request interceptor: Attach JWT token and implement retry logic
api.interceptors.request.use(
    async (config) => {
        try {
            const token = await AsyncStorage.getItem('token');
            if (token) {
                config.headers.Authorization = `Bearer ${token}`;
            }
        } catch (e) {
            console.warn('Failed to retrieve token:', e);
        }
        console.log(`[API] ${config.method.toUpperCase()} ${config.url}`);
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor: Handle 401 with automatic token refresh
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        
        // Handle 401 Unauthorized - attempt token refresh
        if (error.response?.status === 401 && !originalRequest._retry) {
            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                }).then(token => {
                    originalRequest.headers.Authorization = `Bearer ${token}`;
                    return api(originalRequest);
                }).catch(err => {
                    return Promise.reject(err);
                });
            }
            
            originalRequest._retry = true;
            isRefreshing = true;
            
            try {
                const userId = await AsyncStorage.getItem('user_id');
                const refreshToken = await AsyncStorage.getItem('refresh_token');
                
                if (!userId || !refreshToken) {
                    // No refresh token available - need to login
                    await AsyncStorage.removeItem('token');
                    await AsyncStorage.removeItem('refresh_token');
                    await AsyncStorage.removeItem('user_id');
                    processQueue(new Error('Session expired. Please login again.'), null);
                    return Promise.reject({
                        ...error,
                        message: 'Session expired. Please login again.'
                    });
                }
                
                // Attempt to refresh the token using base axios to avoid interceptor loop
                const refreshResponse = await axios.post(`${Config.API_BASE_URL}/api/auth/refresh`, {
                    user_id: userId,
                    refresh_token: refreshToken
                });
                
                if (refreshResponse.data.success) {
                    const newToken = refreshResponse.data.access_token;
                    await AsyncStorage.setItem('token', newToken);
                    
                    // Update authorization header and retry original request
                    originalRequest.headers.Authorization = `Bearer ${newToken}`;
                    processQueue(null, newToken);
                    return api(originalRequest);
                } else {
                    // Refresh failed - need to login again
                    await AsyncStorage.removeItem('token');
                    await AsyncStorage.removeItem('refresh_token');
                    await AsyncStorage.removeItem('user_id');
                    processQueue(new Error(refreshResponse.data.error || 'Token refresh failed'), null);
                    return Promise.reject({
                        ...error,
                        message: 'Session expired. Please login again.'
                    });
                }
            } catch (refreshError) {
                console.error('Token refresh failed:', refreshError);
                
                // If the error is a network error or a 5xx server error, DO NOT clear tokens.
                // The DB might be temporarily down, so we keep the session for later.
                if (!refreshError.response || refreshError.response.status >= 500) {
                    processQueue(refreshError, null);
                    return Promise.reject({
                        ...error,
                        message: 'Server temporarily unavailable. Please try again later.'
                    });
                }
                
                // For 4xx errors (like 401 Invalid refresh token), clear stored tokens
                await AsyncStorage.removeItem('token');
                await AsyncStorage.removeItem('refresh_token');
                await AsyncStorage.removeItem('user_id');
                processQueue(refreshError, null);
                return Promise.reject({
                    ...error,
                    message: 'Session expired. Please login again.'
                });
            }
        }
        
        // Network error - attempt retry
        if (!error.response) {
            console.warn('[API] Network error detected:', error.message);
            console.warn('[API] Error code:', error.code);
            console.warn('[API] Trying to connect to:', Config.API_BASE_URL);
        }
        
        return Promise.reject(error);
    }
);

export default api;

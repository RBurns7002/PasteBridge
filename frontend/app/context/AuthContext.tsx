import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import * as SecureStore from 'expo-secure-store';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const EXPO_PUBLIC_BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const TOKEN_KEY = 'pastebridge_auth_token';
const USER_KEY = 'pastebridge_user';
const PUSH_TOKEN_KEY = 'pastebridge_push_token';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export interface User {
  id: string;
  email: string;
  name: string;
  account_type: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (email: string, password: string, name: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  updateProfile: (name: string) => Promise<{ success: boolean; error?: string }>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<{ success: boolean; error?: string }>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Storage helpers that work on both web and native
async function setSecureItem(key: string, value: string) {
  if (Platform.OS === 'web') {
    await AsyncStorage.setItem(key, value);
  } else {
    await SecureStore.setItemAsync(key, value);
  }
}

async function getSecureItem(key: string): Promise<string | null> {
  if (Platform.OS === 'web') {
    return await AsyncStorage.getItem(key);
  } else {
    return await SecureStore.getItemAsync(key);
  }
}

async function deleteSecureItem(key: string) {
  if (Platform.OS === 'web') {
    await AsyncStorage.removeItem(key);
  } else {
    await SecureStore.deleteItemAsync(key);
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadStoredAuth();
  }, []);

  const loadStoredAuth = async () => {
    try {
      const storedToken = await getSecureItem(TOKEN_KEY);
      const storedUser = await getSecureItem(USER_KEY);

      if (storedToken && storedUser) {
        // Validate token with server
        const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/auth/me`, {
          headers: { Authorization: `Bearer ${storedToken}` },
        });

        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
          setToken(storedToken);
        } else {
          // Token invalid, clear storage
          await deleteSecureItem(TOKEN_KEY);
          await deleteSecureItem(USER_KEY);
        }
      }
    } catch (err) {
      console.error('Error loading auth:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const registerPushNotifications = async (authToken: string) => {
    if (Platform.OS === 'web') return;
    try {
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }
      if (finalStatus !== 'granted') return;

      const pushTokenData = await Notifications.getExpoPushTokenAsync();
      const pushToken = pushTokenData.data;

      // Store locally to avoid re-registering
      const stored = await getSecureItem(PUSH_TOKEN_KEY);
      if (stored === pushToken) return;

      await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/auth/push-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ token: pushToken }),
      });
      await setSecureItem(PUSH_TOKEN_KEY, pushToken);
    } catch (err) {
      console.warn('Push notification registration failed:', err);
    }
  };

  const login = async (email: string, password: string) => {
    try {
      const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (response.ok) {
        await setSecureItem(TOKEN_KEY, data.token);
        await setSecureItem(USER_KEY, JSON.stringify(data.user));
        setUser(data.user);
        setToken(data.token);
        return { success: true };
      } else {
        return { success: false, error: data.detail || 'Login failed' };
      }
    } catch (err) {
      return { success: false, error: 'Connection error' };
    }
  };

  const register = async (email: string, password: string, name: string) => {
    try {
      const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name }),
      });

      const data = await response.json();

      if (response.ok) {
        await setSecureItem(TOKEN_KEY, data.token);
        await setSecureItem(USER_KEY, JSON.stringify(data.user));
        setUser(data.user);
        setToken(data.token);
        return { success: true };
      } else {
        return { success: false, error: data.detail || 'Registration failed' };
      }
    } catch (err) {
      return { success: false, error: 'Connection error' };
    }
  };

  const logout = async () => {
    await deleteSecureItem(TOKEN_KEY);
    await deleteSecureItem(USER_KEY);
    setUser(null);
    setToken(null);
  };

  const updateProfile = async (name: string) => {
    if (!token) return { success: false, error: 'Not authenticated' };

    try {
      const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/auth/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ name }),
      });

      const data = await response.json();

      if (response.ok) {
        setUser(data);
        await setSecureItem(USER_KEY, JSON.stringify(data));
        return { success: true };
      } else {
        return { success: false, error: data.detail || 'Update failed' };
      }
    } catch (err) {
      return { success: false, error: 'Connection error' };
    }
  };

  const changePassword = async (currentPassword: string, newPassword: string) => {
    if (!token) return { success: false, error: 'Not authenticated' };

    try {
      const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/auth/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });

      const data = await response.json();

      if (response.ok) {
        return { success: true };
      } else {
        return { success: false, error: data.detail || 'Password change failed' };
      }
    } catch (err) {
      return { success: false, error: 'Connection error' };
    }
  };

  return (
    <AuthContext.Provider
      value={{ user, token, isLoading, login, register, logout, updateProfile, changePassword }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

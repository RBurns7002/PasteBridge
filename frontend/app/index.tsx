import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Share,
  Platform,
  Alert,
  Vibration,
  FlatList,
  Modal,
  TextInput,
  KeyboardAvoidingView,
  ScrollView,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as Clipboard from 'expo-clipboard';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuth } from './context/AuthContext';

const EXPO_PUBLIC_BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const STORAGE_KEY = 'pastebridge_current_session';
const HISTORY_KEY = 'pastebridge_notepad_history';
const EXPIRATION_WARNING_DAYS = 7;

interface NotepadEntry {
  text: string;
  timestamp: string;
}

interface NotepadSession {
  id: string;
  code: string;
  entries: NotepadEntry[];
  created_at: string;
  updated_at: string;
  account_type: string;
  expires_at: string | null;
  days_remaining: number | null;
  is_expiring_soon: boolean;
  user_id: string | null;
}

interface NotepadHistoryItem {
  code: string;
  created_at: string;
  last_used: string;
  entry_count: number;
  days_remaining?: number;
  is_expiring_soon?: boolean;
  user_id?: string;
}

export default function Index() {
  const { user, token, isLoading: authLoading, login, register, logout } = useAuth();
  
  const [session, setSession] = useState<NotepadSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [lastCaptured, setLastCaptured] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [historyModalVisible, setHistoryModalVisible] = useState(false);
  const [history, setHistory] = useState<NotepadHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  
  // Auth modal state
  const [authModalVisible, setAuthModalVisible] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authName, setAuthName] = useState('');
  const [authError, setAuthError] = useState('');
  const [authLoading2, setAuthLoading2] = useState(false);

  // Claim all modal state
  const [claimModalVisible, setClaimModalVisible] = useState(false);
  const [claimableCount, setClaimableCount] = useState(0);
  const [claiming, setClaiming] = useState(false);

  // Profile modal state
  const [profileModalVisible, setProfileModalVisible] = useState(false);

  useEffect(() => {
    if (!authLoading) {
      loadOrCreateSession();
    }
  }, [authLoading, user]);

  const loadHistory = async (): Promise<NotepadHistoryItem[]> => {
    try {
      const historyJson = await AsyncStorage.getItem(HISTORY_KEY);
      if (historyJson) {
        return JSON.parse(historyJson);
      }
    } catch (err) {
      console.error('Error loading history:', err);
    }
    return [];
  };

  const saveToHistory = async (notepad: NotepadSession) => {
    try {
      const currentHistory = await loadHistory();
      const existingIndex = currentHistory.findIndex(h => h.code === notepad.code);
      
      const historyItem: NotepadHistoryItem = {
        code: notepad.code,
        created_at: notepad.created_at,
        last_used: new Date().toISOString(),
        entry_count: notepad.entries.length,
        days_remaining: notepad.days_remaining || undefined,
        is_expiring_soon: notepad.is_expiring_soon || false,
      };
      
      if (existingIndex >= 0) {
        currentHistory[existingIndex] = historyItem;
      } else {
        currentHistory.unshift(historyItem);
      }
      
      const trimmedHistory = currentHistory.slice(0, 50);
      await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(trimmedHistory));
      setHistory(trimmedHistory);
    } catch (err) {
      console.error('Error saving to history:', err);
    }
  };

  const removeFromHistory = async (code: string) => {
    try {
      const currentHistory = await loadHistory();
      const filtered = currentHistory.filter(h => h.code !== code);
      await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(filtered));
      setHistory(filtered);
    } catch (err) {
      console.error('Error removing from history:', err);
    }
  };

  const loadOrCreateSession = async () => {
    try {
      setLoading(true);
      setError('');

      const savedHistory = await loadHistory();
      setHistory(savedHistory);

      const savedSession = await AsyncStorage.getItem(STORAGE_KEY);
      if (savedSession) {
        const parsed = JSON.parse(savedSession);
        const headers: any = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        
        const response = await fetch(
          `${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${parsed.code}`,
          { headers }
        );
        if (response.ok) {
          const data = await response.json();
          setSession(data);
          await saveToHistory(data);
          setLoading(false);
          return;
        } else if (response.status === 410) {
          await AsyncStorage.removeItem(STORAGE_KEY);
          await removeFromHistory(parsed.code);
        }
      }

      await createNewSession();
    } catch (err) {
      console.error('Error loading session:', err);
      setError('Failed to connect');
    } finally {
      setLoading(false);
    }
  };

  const createNewSession = async () => {
    try {
      setError('');
      const headers: any = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      
      const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/notepad`, {
        method: 'POST',
        headers,
      });

      if (!response.ok) throw new Error('Failed to create notepad');

      const data = await response.json();
      setSession(data);
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      await saveToHistory(data);
      return data;
    } catch (err) {
      console.error('Error creating session:', err);
      throw err;
    }
  };

  const switchToNotepad = async (code: string) => {
    try {
      setLoading(true);
      setHistoryModalVisible(false);
      setError('');

      const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${code}`);
      
      if (response.status === 410) {
        await removeFromHistory(code);
        Alert.alert('Expired', 'This notepad has expired and is no longer available.');
        setLoading(false);
        return;
      }
      
      if (!response.ok) {
        await removeFromHistory(code);
        setError('Notepad not found');
        setLoading(false);
        return;
      }

      const data = await response.json();
      setSession(data);
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      await saveToHistory(data);
      setLastCaptured('');
    } catch (err) {
      console.error('Error switching notepad:', err);
      setError('Failed to load notepad');
    } finally {
      setLoading(false);
    }
  };

  const captureAndSend = useCallback(async () => {
    if (!session) return;

    try {
      setSending(true);
      setError('');
      setSuccessMessage('');

      const clipboardText = await Clipboard.getStringAsync();

      if (!clipboardText || clipboardText.trim() === '') {
        setError('Clipboard empty');
        Vibration.vibrate(100);
        return;
      }

      if (clipboardText === lastCaptured) {
        setError('Already sent');
        return;
      }

      const response = await fetch(
        `${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${session.code}/append`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: clipboardText }),
        }
      );

      if (response.status === 410) {
        setError('Notepad expired');
        Alert.alert('Expired', 'This notepad has expired. Please create a new one.');
        return;
      }

      if (!response.ok) throw new Error('Failed to send');

      const updatedNotepad = await response.json();
      setSession(updatedNotepad);
      setLastCaptured(clipboardText);
      setSuccessMessage('Sent!');
      Vibration.vibrate(50);

      await saveToHistory(updatedNotepad);

      setTimeout(() => setSuccessMessage(''), 2000);
    } catch (err) {
      console.error('Error capturing:', err);
      setError('Failed to send');
      Vibration.vibrate(100);
    } finally {
      setSending(false);
    }
  }, [session, lastCaptured]);

  const shareCode = async () => {
    if (!session) return;
    try {
      await Share.share({
        message: `My PasteBridge code: ${session.code}\n\nOpen ${EXPO_PUBLIC_BACKEND_URL}/api/ and enter the code to view.`,
      });
    } catch (err) {
      console.error('Error sharing:', err);
    }
  };

  const copyCode = async () => {
    if (!session) return;
    await Clipboard.setStringAsync(session.code);
    setSuccessMessage('Code copied!');
    Vibration.vibrate(50);
    setTimeout(() => setSuccessMessage(''), 2000);
  };

  const clearNotepad = async () => {
    if (!session) return;

    Alert.alert('Clear Notepad', 'Clear all entries?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Clear',
        style: 'destructive',
        onPress: async () => {
          try {
            await fetch(
              `${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${session.code}`,
              { method: 'DELETE' }
            );
            const updatedSession = { ...session, entries: [] };
            setSession(updatedSession);
            setLastCaptured('');
            await saveToHistory(updatedSession);
            setSuccessMessage('Cleared!');
            setTimeout(() => setSuccessMessage(''), 2000);
          } catch (err) {
            setError('Failed to clear');
          }
        },
      },
    ]);
  };

  const startNewSession = async () => {
    Alert.alert('New Notepad', 'Create a new notepad? Your current notepad will be saved in history.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Create New',
        onPress: async () => {
          setLoading(true);
          await createNewSession();
          setLastCaptured('');
          setLoading(false);
        },
      },
    ]);
  };

  const openHistoryModal = async () => {
    setLoadingHistory(true);
    const savedHistory = await loadHistory();
    
    const validatedHistory: NotepadHistoryItem[] = [];
    const knownCodes = new Set<string>();

    for (const item of savedHistory) {
      try {
        const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${item.code}`);
        if (response.ok) {
          const data = await response.json();
          knownCodes.add(item.code);
          validatedHistory.push({
            ...item,
            entry_count: data.entries.length,
            days_remaining: data.days_remaining,
            is_expiring_soon: data.is_expiring_soon,
            user_id: data.user_id || undefined,
          });
        }
      } catch {
        // Skip invalid notepads
      }
    }

    // Merge server-side user notepads that aren't in local history
    if (token) {
      try {
        const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/auth/notepads`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (response.ok) {
          const serverNotepads = await response.json();
          for (const np of serverNotepads) {
            if (!knownCodes.has(np.code)) {
              validatedHistory.push({
                code: np.code,
                created_at: np.created_at,
                last_used: np.updated_at,
                entry_count: np.entries.length,
                days_remaining: np.days_remaining,
                is_expiring_soon: np.is_expiring_soon,
                user_id: np.user_id,
              });
            }
          }
        }
      } catch {
        // Server fetch failed, continue with local only
      }
    }
    
    await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(validatedHistory));
    setHistory(validatedHistory);
    setLoadingHistory(false);
    setHistoryModalVisible(true);
  };

  const deleteFromHistory = (code: string) => {
    if (session?.code === code) {
      Alert.alert('Cannot Delete', 'This is your current notepad. Switch to another notepad first.');
      return;
    }

    Alert.alert('Remove from History', 'Remove this notepad from your history?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: () => removeFromHistory(code),
      },
    ]);
  };

  const handleAuth = async () => {
    setAuthError('');
    setAuthLoading2(true);

    try {
      let result;
      if (authMode === 'login') {
        result = await login(authEmail, authPassword);
      } else {
        result = await register(authEmail, authPassword, authName);
      }

      if (result.success) {
        setAuthModalVisible(false);
        setAuthEmail('');
        setAuthPassword('');
        setAuthName('');
        // Check for claimable guest notepads from local history
        const localHistory = await loadHistory();
        const unlinkedCodes = localHistory.filter(h => !h.user_id).map(h => h.code);
        if (unlinkedCodes.length > 0) {
          setClaimableCount(unlinkedCodes.length);
          setClaimModalVisible(true);
        }
        loadOrCreateSession();
      } else {
        setAuthError(result.error || (authMode === 'login' ? 'Login failed' : 'Registration failed'));
      }
    } finally {
      setAuthLoading2(false);
    }
  };

  const handleLogout = () => {
    Alert.alert('Logout', 'Are you sure you want to logout?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Logout',
        style: 'destructive',
        onPress: async () => {
          await logout();
          setProfileModalVisible(false);
        },
      },
    ]);
  };

  const linkCurrentNotepad = async () => {
    if (!session || !token) return;

    try {
      const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/auth/link-notepad`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ code: session.code }),
      });

      const data = await response.json();

      if (response.ok) {
        setSession(data);
        await saveToHistory(data);
        setSuccessMessage('Notepad linked!');
        setTimeout(() => setSuccessMessage(''), 2000);
      } else {
        if (data.detail?.includes('already linked')) {
          setSuccessMessage('Already linked');
          setTimeout(() => setSuccessMessage(''), 2000);
        } else {
          setError(data.detail || 'Failed to link');
        }
      }
    } catch (err) {
      setError('Connection error');
    }
  };

  const claimAllNotepads = async () => {
    if (!token) return;
    setClaiming(true);

    try {
      const localHistory = await loadHistory();
      const codes = localHistory.map(h => h.code);

      const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/auth/link-notepads`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ codes }),
      });

      if (response.ok) {
        const data = await response.json();
        setClaimModalVisible(false);
        setSuccessMessage(`${data.linked_count} notepad${data.linked_count !== 1 ? 's' : ''} claimed!`);
        setTimeout(() => setSuccessMessage(''), 3000);
        // Refresh session to pick up updated user_id
        loadOrCreateSession();
      } else {
        setError('Failed to claim notepads');
        setClaimModalVisible(false);
      }
    } catch (err) {
      setError('Connection error');
      setClaimModalVisible(false);
    } finally {
      setClaiming(false);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatExpirationDate = (dateStr: string | null) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: 'numeric'
    });
  };

  const renderHistoryItem = ({ item }: { item: NotepadHistoryItem }) => {
    const isActive = session?.code === item.code;
    const isExpiringSoon = item.is_expiring_soon || false;
    
    return (
      <TouchableOpacity
        style={[
          styles.historyItem, 
          isActive && styles.historyItemActive,
          isExpiringSoon && styles.historyItemExpiring
        ]}
        onPress={() => switchToNotepad(item.code)}
        onLongPress={() => deleteFromHistory(item.code)}
      >
        <View style={styles.historyItemLeft}>
          <View style={styles.historyCodeRow}>
            <Text style={styles.historyCode}>{item.code}</Text>
            {isActive && (
              <View style={styles.activeBadge}>
                <Text style={styles.activeBadgeText}>Active</Text>
              </View>
            )}
            {isExpiringSoon && !isActive && (
              <View style={styles.expiringBadge}>
                <Text style={styles.expiringBadgeText}>Expiring</Text>
              </View>
            )}
          </View>
          <Text style={styles.historyMeta}>
            {item.entry_count} entries • Last used {formatDate(item.last_used)}
          </Text>
          {item.days_remaining !== undefined && (
            <Text style={[
              styles.historyExpiration,
              isExpiringSoon && styles.historyExpirationWarning
            ]}>
              {item.days_remaining} days remaining
            </Text>
          )}
        </View>
        <Ionicons name="chevron-forward" size={20} color="#52525b" />
      </TouchableOpacity>
    );
  };

  if (loading || authLoading) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="light" />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#60a5fa" />
          <Text style={styles.loadingText}>Loading PasteBridge...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>PasteBridge</Text>
        <View style={styles.headerRight}>
          <TouchableOpacity
            style={styles.headerBtn}
            onPress={openHistoryModal}
          >
            <Ionicons name="time-outline" size={22} color="#60a5fa" />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.headerBtn}
            onPress={() => user ? setProfileModalVisible(true) : setAuthModalVisible(true)}
          >
            <Ionicons 
              name={user ? "person" : "person-outline"} 
              size={22} 
              color={user ? "#22c55e" : "#60a5fa"} 
            />
          </TouchableOpacity>
        </View>
      </View>

      {/* User Status Banner */}
      {user ? (
        <View style={styles.userBanner}>
          <Ionicons name="checkmark-circle" size={16} color="#22c55e" />
          <Text style={styles.userBannerText}>Logged in as {user.name || user.email}</Text>
        </View>
      ) : (
        <TouchableOpacity 
          style={styles.guestBanner}
          onPress={() => setAuthModalVisible(true)}
        >
          <Ionicons name="person-outline" size={16} color="#fbbf24" />
          <Text style={styles.guestBannerText}>Guest mode • Tap to sign up for longer storage</Text>
        </TouchableOpacity>
      )}

      {/* Expiration Warning Banner */}
      {session?.is_expiring_soon && (
        <View style={styles.expirationBanner}>
          <Ionicons name="warning" size={18} color="#fbbf24" />
          <Text style={styles.expirationBannerText}>
            Expires in {session.days_remaining} day{session.days_remaining !== 1 ? 's' : ''} • {formatExpirationDate(session.expires_at)}
          </Text>
        </View>
      )}

      {/* Code Display Card */}
      {session && (
        <View style={styles.codeCard}>
          <Text style={styles.codeLabel}>YOUR CODE</Text>
          <TouchableOpacity onPress={copyCode} activeOpacity={0.7}>
            <Text style={styles.codeText}>{session.code}</Text>
          </TouchableOpacity>
          <Text style={styles.codeHint}>Type this at the website on your PC</Text>
          
          {!session.is_expiring_soon && session.days_remaining && (
            <Text style={styles.expirationInfo}>
              Available for {session.days_remaining} days
            </Text>
          )}
          
          <View style={styles.codeActions}>
            <TouchableOpacity style={styles.codeActionBtn} onPress={copyCode}>
              <Ionicons name="copy-outline" size={18} color="#60a5fa" />
              <Text style={styles.codeActionText}>Copy</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.codeActionBtn} onPress={shareCode}>
              <Ionicons name="share-outline" size={18} color="#60a5fa" />
              <Text style={styles.codeActionText}>Share</Text>
            </TouchableOpacity>
            {user && !session.user_id && (
              <TouchableOpacity style={styles.codeActionBtn} onPress={linkCurrentNotepad}>
                <Ionicons name="link-outline" size={18} color="#60a5fa" />
                <Text style={styles.codeActionText}>Link</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      )}

      {/* Main Capture Button */}
      <TouchableOpacity
        style={[
          styles.captureButton,
          sending && styles.captureButtonDisabled,
        ]}
        onPress={captureAndSend}
        disabled={sending}
        activeOpacity={0.8}
      >
        {sending ? (
          <ActivityIndicator size="large" color="#ffffff" />
        ) : (
          <>
            <Ionicons name="send" size={48} color="#ffffff" />
            <Text style={styles.captureButtonText}>Capture & Send</Text>
          </>
        )}
      </TouchableOpacity>

      {/* Status */}
      {error ? (
        <View style={styles.statusContainer}>
          <Ionicons name="alert-circle" size={18} color="#ef4444" />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : successMessage ? (
        <View style={styles.statusContainer}>
          <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
          <Text style={styles.successText}>{successMessage}</Text>
        </View>
      ) : (
        <View style={styles.statusContainer}>
          <Text style={styles.hintText}>
            {session?.entries.length || 0} entries sent
          </Text>
        </View>
      )}

      {/* Bottom Actions */}
      <View style={styles.bottomActions}>
        <TouchableOpacity style={styles.bottomBtn} onPress={clearNotepad}>
          <Ionicons name="trash-outline" size={20} color="#71717a" />
          <Text style={styles.bottomBtnText}>Clear</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.bottomBtn} onPress={startNewSession}>
          <Ionicons name="add-circle-outline" size={20} color="#71717a" />
          <Text style={styles.bottomBtnText}>New Notepad</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.bottomBtn} onPress={openHistoryModal}>
          <Ionicons name="folder-outline" size={20} color="#71717a" />
          <Text style={styles.bottomBtnText}>History</Text>
        </TouchableOpacity>
      </View>

      {/* Instructions */}
      <View style={styles.instructions}>
        <Text style={styles.instructionsTitle}>How to use:</Text>
        <Text style={styles.instructionsText}>
          1. Go to the website on your PC{"\n"}
          2. Enter the code shown above{"\n"}
          3. Copy text on your phone{"\n"}
          4. Tap "Capture & Send"
        </Text>
      </View>

      {/* Auth Modal */}
      <Modal
        visible={authModalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setAuthModalVisible(false)}
      >
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <View style={styles.authModalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                {authMode === 'login' ? 'Sign In' : 'Create Account'}
              </Text>
              <TouchableOpacity
                style={styles.modalCloseBtn}
                onPress={() => setAuthModalVisible(false)}
              >
                <Ionicons name="close" size={24} color="#a1a1aa" />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.authForm}>
              {authMode === 'register' && (
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Name</Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder="Your name"
                    placeholderTextColor="#52525b"
                    value={authName}
                    onChangeText={setAuthName}
                    autoCapitalize="words"
                  />
                </View>
              )}

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Email</Text>
                <TextInput
                  style={styles.textInput}
                  placeholder="you@example.com"
                  placeholderTextColor="#52525b"
                  value={authEmail}
                  onChangeText={setAuthEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.inputLabel}>Password</Text>
                <TextInput
                  style={styles.textInput}
                  placeholder="••••••••"
                  placeholderTextColor="#52525b"
                  value={authPassword}
                  onChangeText={setAuthPassword}
                  secureTextEntry
                />
              </View>

              {authError ? (
                <Text style={styles.authError}>{authError}</Text>
              ) : null}

              <TouchableOpacity
                style={[styles.authSubmitBtn, authLoading2 && styles.authSubmitBtnDisabled]}
                onPress={handleAuth}
                disabled={authLoading2}
              >
                {authLoading2 ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.authSubmitBtnText}>
                    {authMode === 'login' ? 'Sign In' : 'Create Account'}
                  </Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.authSwitchBtn}
                onPress={() => {
                  setAuthMode(authMode === 'login' ? 'register' : 'login');
                  setAuthError('');
                }}
              >
                <Text style={styles.authSwitchText}>
                  {authMode === 'login' 
                    ? "Don't have an account? Sign up" 
                    : 'Already have an account? Sign in'}
                </Text>
              </TouchableOpacity>

              <View style={styles.authBenefits}>
                <Text style={styles.authBenefitsTitle}>Benefits of signing up:</Text>
                <Text style={styles.authBenefit}>• Extended notepad storage (1 year)</Text>
                <Text style={styles.authBenefit}>• Sync notepads across devices</Text>
                <Text style={styles.authBenefit}>• Link existing notepads</Text>
              </View>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Profile Modal */}
      <Modal
        visible={profileModalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setProfileModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.profileModalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Profile</Text>
              <TouchableOpacity
                style={styles.modalCloseBtn}
                onPress={() => setProfileModalVisible(false)}
              >
                <Ionicons name="close" size={24} color="#a1a1aa" />
              </TouchableOpacity>
            </View>

            {user && (
              <View style={styles.profileInfo}>
                <View style={styles.profileAvatar}>
                  <Ionicons name="person" size={40} color="#60a5fa" />
                </View>
                <Text style={styles.profileName}>{user.name || 'User'}</Text>
                <Text style={styles.profileEmail}>{user.email}</Text>
                <View style={styles.profileBadge}>
                  <Text style={styles.profileBadgeText}>
                    {user.account_type === 'premium' ? '⭐ Premium' : '👤 User'}
                  </Text>
                </View>
              </View>
            )}

            <TouchableOpacity
              style={styles.profileLogoutBtn}
              onPress={handleLogout}
            >
              <Ionicons name="log-out-outline" size={20} color="#ef4444" />
              <Text style={styles.profileLogoutText}>Logout</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* History Modal */}
      <Modal
        visible={historyModalVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setHistoryModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Your Notepads</Text>
              <TouchableOpacity
                style={styles.modalCloseBtn}
                onPress={() => setHistoryModalVisible(false)}
              >
                <Ionicons name="close" size={24} color="#a1a1aa" />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSubtitle}>
              {user ? 'User notepads last 1 year' : 'Guest notepads expire after 90 days'}
            </Text>

            {loadingHistory ? (
              <View style={styles.modalLoading}>
                <ActivityIndicator size="large" color="#60a5fa" />
                <Text style={styles.modalLoadingText}>Loading notepads...</Text>
              </View>
            ) : history.length === 0 ? (
              <View style={styles.modalEmpty}>
                <Ionicons name="folder-open-outline" size={48} color="#52525b" />
                <Text style={styles.modalEmptyText}>No notepads yet</Text>
                <Text style={styles.modalEmptyHint}>Create your first notepad to get started</Text>
              </View>
            ) : (
              <FlatList
                data={history}
                renderItem={renderHistoryItem}
                keyExtractor={(item) => item.code}
                style={styles.historyList}
                showsVerticalScrollIndicator={false}
              />
            )}

            <TouchableOpacity
              style={styles.newNotepadBtn}
              onPress={() => {
                setHistoryModalVisible(false);
                startNewSession();
              }}
            >
              <Ionicons name="add" size={20} color="#ffffff" />
              <Text style={styles.newNotepadBtnText}>Create New Notepad</Text>
            </TouchableOpacity>

            <Text style={styles.modalHint}>Long press to remove from history</Text>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f1a',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
  },
  loadingText: {
    color: '#a1a1aa',
    fontSize: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  title: {
    fontSize: 26,
    fontWeight: 'bold',
    color: '#60a5fa',
  },
  headerRight: {
    flexDirection: 'row',
    gap: 8,
  },
  headerBtn: {
    padding: 8,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    borderRadius: 10,
  },
  userBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginHorizontal: 20,
    paddingVertical: 8,
    backgroundColor: 'rgba(34, 197, 94, 0.1)',
    borderRadius: 8,
    marginBottom: 8,
  },
  userBannerText: {
    color: '#22c55e',
    fontSize: 13,
  },
  guestBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginHorizontal: 20,
    paddingVertical: 8,
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    borderRadius: 8,
    marginBottom: 8,
  },
  guestBannerText: {
    color: '#fbbf24',
    fontSize: 13,
  },
  expirationBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginHorizontal: 20,
    marginBottom: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.3)',
  },
  expirationBannerText: {
    color: '#fbbf24',
    fontSize: 14,
    fontWeight: '500',
  },
  codeCard: {
    marginHorizontal: 20,
    backgroundColor: 'rgba(96, 165, 250, 0.08)',
    borderRadius: 20,
    padding: 20,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(96, 165, 250, 0.2)',
  },
  codeLabel: {
    fontSize: 11,
    color: '#71717a',
    letterSpacing: 2,
    marginBottom: 6,
  },
  codeText: {
    fontSize: 32,
    fontWeight: '700',
    color: '#60a5fa',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    letterSpacing: 2,
  },
  codeHint: {
    fontSize: 12,
    color: '#52525b',
    marginTop: 6,
  },
  expirationInfo: {
    fontSize: 11,
    color: '#71717a',
    marginTop: 6,
  },
  codeActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 14,
  },
  codeActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: 12,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    borderRadius: 8,
  },
  codeActionText: {
    color: '#60a5fa',
    fontSize: 13,
    fontWeight: '500',
  },
  captureButton: {
    marginHorizontal: 20,
    marginTop: 20,
    backgroundColor: '#3b82f6',
    borderRadius: 24,
    paddingVertical: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  captureButtonDisabled: {
    backgroundColor: '#1e3a5f',
  },
  captureButtonText: {
    color: '#ffffff',
    fontSize: 20,
    fontWeight: 'bold',
    marginTop: 10,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 14,
    height: 22,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 13,
  },
  successText: {
    color: '#22c55e',
    fontSize: 13,
    fontWeight: '600',
  },
  hintText: {
    color: '#52525b',
    fontSize: 13,
  },
  bottomActions: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 20,
    marginTop: 20,
  },
  bottomBtn: {
    alignItems: 'center',
    gap: 4,
  },
  bottomBtnText: {
    color: '#71717a',
    fontSize: 11,
  },
  instructions: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(0,0,0,0.6)',
    padding: 16,
  },
  instructionsTitle: {
    color: '#71717a',
    fontSize: 11,
    fontWeight: '600',
    marginBottom: 4,
  },
  instructionsText: {
    color: '#52525b',
    fontSize: 10,
    lineHeight: 16,
  },

  // Modal Styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#1a1a2e',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 20,
    paddingBottom: 40,
    maxHeight: '80%',
  },
  authModalContent: {
    backgroundColor: '#1a1a2e',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 20,
    paddingBottom: 20,
    maxHeight: '90%',
  },
  profileModalContent: {
    backgroundColor: '#1a1a2e',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 20,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    marginBottom: 4,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#ffffff',
  },
  modalSubtitle: {
    fontSize: 13,
    color: '#71717a',
    paddingHorizontal: 20,
    marginBottom: 16,
  },
  modalCloseBtn: {
    padding: 4,
  },
  modalLoading: {
    padding: 40,
    alignItems: 'center',
    gap: 16,
  },
  modalLoadingText: {
    color: '#a1a1aa',
    fontSize: 14,
  },
  modalEmpty: {
    padding: 40,
    alignItems: 'center',
    gap: 12,
  },
  modalEmptyText: {
    color: '#a1a1aa',
    fontSize: 16,
    fontWeight: '500',
  },
  modalEmptyHint: {
    color: '#52525b',
    fontSize: 14,
  },
  historyList: {
    paddingHorizontal: 20,
    maxHeight: 400,
  },
  historyItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
  },
  historyItemActive: {
    backgroundColor: 'rgba(96, 165, 250, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(96, 165, 250, 0.3)',
  },
  historyItemExpiring: {
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.3)',
  },
  historyItemLeft: {
    flex: 1,
  },
  historyCodeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  historyCode: {
    fontSize: 18,
    fontWeight: '600',
    color: '#60a5fa',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  activeBadge: {
    backgroundColor: '#22c55e',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  activeBadgeText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: '600',
  },
  expiringBadge: {
    backgroundColor: '#f59e0b',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  expiringBadgeText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: '600',
  },
  historyMeta: {
    fontSize: 12,
    color: '#71717a',
    marginTop: 4,
  },
  historyExpiration: {
    fontSize: 11,
    color: '#52525b',
    marginTop: 2,
  },
  historyExpirationWarning: {
    color: '#fbbf24',
  },
  newNotepadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#3b82f6',
    marginHorizontal: 20,
    marginTop: 16,
    paddingVertical: 14,
    borderRadius: 12,
  },
  newNotepadBtnText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
  modalHint: {
    color: '#52525b',
    fontSize: 12,
    textAlign: 'center',
    marginTop: 16,
  },

  // Auth Modal Styles
  authForm: {
    paddingHorizontal: 20,
  },
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    color: '#a1a1aa',
    fontSize: 14,
    marginBottom: 8,
  },
  textInput: {
    backgroundColor: 'rgba(0,0,0,0.3)',
    borderRadius: 12,
    padding: 14,
    color: '#ffffff',
    fontSize: 16,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  authError: {
    color: '#ef4444',
    fontSize: 14,
    marginBottom: 16,
    textAlign: 'center',
  },
  authSubmitBtn: {
    backgroundColor: '#3b82f6',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 8,
  },
  authSubmitBtnDisabled: {
    backgroundColor: '#1e3a5f',
  },
  authSubmitBtnText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
  authSwitchBtn: {
    marginTop: 16,
    alignItems: 'center',
  },
  authSwitchText: {
    color: '#60a5fa',
    fontSize: 14,
  },
  authBenefits: {
    marginTop: 24,
    padding: 16,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    borderRadius: 12,
  },
  authBenefitsTitle: {
    color: '#60a5fa',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  authBenefit: {
    color: '#a1a1aa',
    fontSize: 13,
    marginBottom: 4,
  },

  // Profile Modal Styles
  profileInfo: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  profileAvatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(96, 165, 250, 0.2)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  profileName: {
    color: '#ffffff',
    fontSize: 20,
    fontWeight: '600',
    marginBottom: 4,
  },
  profileEmail: {
    color: '#71717a',
    fontSize: 14,
    marginBottom: 12,
  },
  profileBadge: {
    backgroundColor: 'rgba(96, 165, 250, 0.2)',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  profileBadgeText: {
    color: '#60a5fa',
    fontSize: 13,
  },
  profileLogoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginHorizontal: 20,
    paddingVertical: 14,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: 12,
  },
  profileLogoutText: {
    color: '#ef4444',
    fontSize: 16,
    fontWeight: '500',
  },
});

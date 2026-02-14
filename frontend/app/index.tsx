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
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as Clipboard from 'expo-clipboard';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';

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
}

interface NotepadHistoryItem {
  code: string;
  created_at: string;
  last_used: string;
  entry_count: number;
  days_remaining?: number;
  is_expiring_soon?: boolean;
}

export default function Index() {
  const [session, setSession] = useState<NotepadSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [lastCaptured, setLastCaptured] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [historyModalVisible, setHistoryModalVisible] = useState(false);
  const [history, setHistory] = useState<NotepadHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    loadOrCreateSession();
  }, []);

  // Load notepad history from storage
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

  // Save notepad to history
  const saveToHistory = async (notepad: NotepadSession) => {
    try {
      const currentHistory = await loadHistory();
      
      // Check if already exists
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
        // Update existing
        currentHistory[existingIndex] = historyItem;
      } else {
        // Add new at the beginning
        currentHistory.unshift(historyItem);
      }
      
      // Keep only last 50 notepads
      const trimmedHistory = currentHistory.slice(0, 50);
      
      await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(trimmedHistory));
      setHistory(trimmedHistory);
    } catch (err) {
      console.error('Error saving to history:', err);
    }
  };

  // Remove notepad from history
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

      // Load history
      const savedHistory = await loadHistory();
      setHistory(savedHistory);

      const savedSession = await AsyncStorage.getItem(STORAGE_KEY);
      if (savedSession) {
        const parsed = JSON.parse(savedSession);
        const response = await fetch(
          `${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${parsed.code}`
        );
        if (response.ok) {
          const data = await response.json();
          setSession(data);
          await saveToHistory(data);
          setLoading(false);
          return;
        } else if (response.status === 410) {
          // Notepad expired, remove from storage and create new
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
      const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/notepad`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
        // Notepad expired
        await removeFromHistory(code);
        Alert.alert('Expired', 'This notepad has expired and is no longer available.');
        setLoading(false);
        return;
      }
      
      if (!response.ok) {
        // Notepad no longer exists, remove from history
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

      // Update history with new entry count
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
    
    // Validate each notepad still exists and update entry counts
    const validatedHistory: NotepadHistoryItem[] = [];
    for (const item of savedHistory) {
      try {
        const response = await fetch(`${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${item.code}`);
        if (response.ok) {
          const data = await response.json();
          validatedHistory.push({
            ...item,
            entry_count: data.entries.length,
            days_remaining: data.days_remaining,
            is_expiring_soon: data.is_expiring_soon,
          });
        }
        // Skip expired (410) or not found (404) notepads
      } catch {
        // Skip invalid notepads
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

  // Loading state
  if (loading) {
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

  // Main UI
  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>PasteBridge</Text>
        <TouchableOpacity
          style={styles.historyBtn}
          onPress={openHistoryModal}
        >
          <Ionicons name="time-outline" size={24} color="#60a5fa" />
        </TouchableOpacity>
      </View>

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
          
          {/* Expiration info (non-warning) */}
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
          4. Tap "Capture & Send"{"\n"}
          5. Text appears on your PC!
        </Text>
      </View>

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
              Guest notepads expire after 90 days
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
    paddingVertical: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#60a5fa',
  },
  historyBtn: {
    padding: 8,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    borderRadius: 10,
  },
  expirationBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginHorizontal: 20,
    marginBottom: 12,
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
    padding: 24,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(96, 165, 250, 0.2)',
  },
  codeLabel: {
    fontSize: 12,
    color: '#71717a',
    letterSpacing: 2,
    marginBottom: 8,
  },
  codeText: {
    fontSize: 36,
    fontWeight: '700',
    color: '#60a5fa',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    letterSpacing: 2,
  },
  codeHint: {
    fontSize: 13,
    color: '#52525b',
    marginTop: 8,
  },
  expirationInfo: {
    fontSize: 12,
    color: '#71717a',
    marginTop: 8,
  },
  codeActions: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 16,
  },
  codeActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 16,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    borderRadius: 8,
  },
  codeActionText: {
    color: '#60a5fa',
    fontSize: 14,
    fontWeight: '500',
  },
  captureButton: {
    marginHorizontal: 20,
    marginTop: 24,
    backgroundColor: '#3b82f6',
    borderRadius: 24,
    paddingVertical: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  captureButtonDisabled: {
    backgroundColor: '#1e3a5f',
  },
  captureButtonText: {
    color: '#ffffff',
    fontSize: 22,
    fontWeight: 'bold',
    marginTop: 12,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 16,
    height: 24,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 14,
  },
  successText: {
    color: '#22c55e',
    fontSize: 14,
    fontWeight: '600',
  },
  hintText: {
    color: '#52525b',
    fontSize: 14,
  },
  bottomActions: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 24,
    marginTop: 24,
  },
  bottomBtn: {
    alignItems: 'center',
    gap: 4,
  },
  bottomBtnText: {
    color: '#71717a',
    fontSize: 12,
  },
  instructions: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(0,0,0,0.6)',
    padding: 20,
  },
  instructionsTitle: {
    color: '#71717a',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 6,
  },
  instructionsText: {
    color: '#52525b',
    fontSize: 11,
    lineHeight: 18,
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
});

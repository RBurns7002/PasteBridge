import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Share,
  Platform,
  Linking,
  Alert,
  Vibration,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as Clipboard from 'expo-clipboard';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';

const EXPO_PUBLIC_BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const STORAGE_KEY = 'pastebridge_session';

interface NotepadEntry {
  text: string;
  timestamp: string;
}

interface NotepadSession {
  id: string;
  slug: string;
  entries: NotepadEntry[];
  created_at: string;
  updated_at: string;
}

export default function Index() {
  const [session, setSession] = useState<NotepadSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [lastCaptured, setLastCaptured] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');

  const webViewUrl = session
    ? `${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${session.slug}/view`
    : '';

  // Load or create session
  useEffect(() => {
    loadOrCreateSession();
  }, []);

  const loadOrCreateSession = async () => {
    try {
      setLoading(true);
      setError('');

      // Try to load existing session
      const savedSession = await AsyncStorage.getItem(STORAGE_KEY);
      if (savedSession) {
        const parsed = JSON.parse(savedSession);
        // Verify session still exists on server
        const response = await fetch(
          `${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${parsed.slug}`
        );
        if (response.ok) {
          const data = await response.json();
          setSession(data);
          setLoading(false);
          return;
        }
      }

      // Create new session
      await createNewSession();
    } catch (err) {
      console.error('Error loading session:', err);
      setError('Failed to connect. Please check your connection.');
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
    } catch (err) {
      console.error('Error creating session:', err);
      throw err;
    }
  };

  const captureAndSend = async () => {
    if (!session) return;

    try {
      setSending(true);
      setError('');
      setSuccessMessage('');

      // Read clipboard
      const clipboardText = await Clipboard.getStringAsync();

      if (!clipboardText || clipboardText.trim() === '') {
        setError('Clipboard is empty');
        Vibration.vibrate(100);
        return;
      }

      // Don't send duplicate
      if (clipboardText === lastCaptured) {
        setError('Already sent this text');
        return;
      }

      // Send to server
      const response = await fetch(
        `${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${session.slug}/append`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: clipboardText }),
        }
      );

      if (!response.ok) throw new Error('Failed to send');

      const updatedNotepad = await response.json();
      setSession(updatedNotepad);
      setLastCaptured(clipboardText);
      setSuccessMessage('Sent!');

      // Haptic feedback
      Vibration.vibrate(50);

      // Clear success message after 2 seconds
      setTimeout(() => setSuccessMessage(''), 2000);
    } catch (err) {
      console.error('Error capturing:', err);
      setError('Failed to send. Please try again.');
      Vibration.vibrate(100);
    } finally {
      setSending(false);
    }
  };

  const shareLink = async () => {
    if (!webViewUrl) return;

    try {
      await Share.share({
        message: `View my clipboard notepad: ${webViewUrl}`,
        url: webViewUrl,
      });
    } catch (err) {
      console.error('Error sharing:', err);
    }
  };

  const copyLink = async () => {
    if (!webViewUrl) return;
    await Clipboard.setStringAsync(webViewUrl);
    setSuccessMessage('Link copied!');
    Vibration.vibrate(50);
    setTimeout(() => setSuccessMessage(''), 2000);
  };

  const openInBrowser = async () => {
    if (!webViewUrl) return;
    try {
      await Linking.openURL(webViewUrl);
    } catch (err) {
      console.error('Error opening browser:', err);
    }
  };

  const clearNotepad = async () => {
    if (!session) return;

    Alert.alert(
      'Clear Notepad',
      'Are you sure you want to clear all entries?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            try {
              await fetch(
                `${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${session.slug}`,
                { method: 'DELETE' }
              );
              setSession({ ...session, entries: [] });
              setLastCaptured('');
              setSuccessMessage('Cleared!');
              setTimeout(() => setSuccessMessage(''), 2000);
            } catch (err) {
              setError('Failed to clear');
            }
          },
        },
      ]
    );
  };

  const startNewSession = async () => {
    Alert.alert(
      'New Session',
      'Start a new notepad session? This will create a new shareable link.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'New Session',
          onPress: async () => {
            setLoading(true);
            await AsyncStorage.removeItem(STORAGE_KEY);
            await createNewSession();
            setLastCaptured('');
            setLoading(false);
          },
        },
      ]
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="light" />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#60a5fa" />
          <Text style={styles.loadingText}>Setting up PasteBridge...</Text>
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
        <Text style={styles.subtitle}>Clipboard to Web Notepad</Text>
      </View>

      {/* Session Info */}
      {session && (
        <View style={styles.sessionCard}>
          <View style={styles.sessionHeader}>
            <Ionicons name="link" size={18} color="#60a5fa" />
            <Text style={styles.sessionSlug}>{session.slug}</Text>
          </View>
          <Text style={styles.entriesCount}>
            {session.entries.length} {session.entries.length === 1 ? 'entry' : 'entries'}
          </Text>
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
            <Ionicons name="clipboard" size={48} color="#ffffff" />
            <Text style={styles.captureButtonText}>Capture & Send</Text>
            <Text style={styles.captureButtonHint}>Tap to send clipboard</Text>
          </>
        )}
      </TouchableOpacity>

      {/* Status Messages */}
      {error ? (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={20} color="#ef4444" />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {successMessage ? (
        <View style={styles.successContainer}>
          <Ionicons name="checkmark-circle" size={20} color="#22c55e" />
          <Text style={styles.successText}>{successMessage}</Text>
        </View>
      ) : null}

      {/* Action Buttons */}
      <View style={styles.actionButtons}>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={copyLink}
          activeOpacity={0.7}
        >
          <Ionicons name="copy-outline" size={24} color="#60a5fa" />
          <Text style={styles.actionButtonText}>Copy Link</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionButton}
          onPress={shareLink}
          activeOpacity={0.7}
        >
          <Ionicons name="share-outline" size={24} color="#60a5fa" />
          <Text style={styles.actionButtonText}>Share</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionButton}
          onPress={openInBrowser}
          activeOpacity={0.7}
        >
          <Ionicons name="open-outline" size={24} color="#60a5fa" />
          <Text style={styles.actionButtonText}>Open Web</Text>
        </TouchableOpacity>
      </View>

      {/* Bottom Actions */}
      <View style={styles.bottomActions}>
        <TouchableOpacity
          style={styles.bottomButton}
          onPress={clearNotepad}
          activeOpacity={0.7}
        >
          <Ionicons name="trash-outline" size={20} color="#a1a1aa" />
          <Text style={styles.bottomButtonText}>Clear Notepad</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.bottomButton}
          onPress={startNewSession}
          activeOpacity={0.7}
        >
          <Ionicons name="add-circle-outline" size={20} color="#a1a1aa" />
          <Text style={styles.bottomButtonText}>New Session</Text>
        </TouchableOpacity>
      </View>

      {/* Instructions */}
      <View style={styles.instructions}>
        <Text style={styles.instructionsTitle}>How to use:</Text>
        <Text style={styles.instructionsText}>
          1. Open the web notepad link on your computer{"\n"}
          2. Copy any text on your phone{"\n"}
          3. Tap "Capture & Send" button{"\n"}
          4. Text appears on the web notepad!
        </Text>
      </View>
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
    alignItems: 'center',
    paddingVertical: 24,
    paddingHorizontal: 20,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#60a5fa',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 14,
    color: '#a1a1aa',
  },
  sessionCard: {
    marginHorizontal: 20,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  sessionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  sessionSlug: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 18,
    color: '#60a5fa',
    fontWeight: '600',
  },
  entriesCount: {
    fontSize: 13,
    color: '#71717a',
    marginLeft: 26,
  },
  captureButton: {
    marginHorizontal: 20,
    backgroundColor: '#3b82f6',
    borderRadius: 24,
    paddingVertical: 40,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#3b82f6',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.4,
    shadowRadius: 16,
    elevation: 8,
  },
  captureButtonDisabled: {
    backgroundColor: '#1e3a5f',
  },
  captureButtonText: {
    color: '#ffffff',
    fontSize: 24,
    fontWeight: 'bold',
    marginTop: 12,
  },
  captureButtonHint: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 14,
    marginTop: 4,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 16,
    paddingHorizontal: 20,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 14,
  },
  successContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 16,
    paddingHorizontal: 20,
  },
  successText: {
    color: '#22c55e',
    fontSize: 14,
    fontWeight: '600',
  },
  actionButtons: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 12,
    marginTop: 32,
    paddingHorizontal: 20,
  },
  actionButton: {
    flex: 1,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    gap: 6,
  },
  actionButtonText: {
    color: '#60a5fa',
    fontSize: 12,
    fontWeight: '500',
  },
  bottomActions: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 24,
    marginTop: 24,
    paddingHorizontal: 20,
  },
  bottomButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  bottomButtonText: {
    color: '#a1a1aa',
    fontSize: 14,
  },
  instructions: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    padding: 20,
  },
  instructionsTitle: {
    color: '#a1a1aa',
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  instructionsText: {
    color: '#71717a',
    fontSize: 12,
    lineHeight: 20,
  },
});

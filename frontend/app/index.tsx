import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Share,
  Platform,
  Linking,
  Alert,
  Vibration,
  Animated,
  Dimensions,
  PanResponder,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as Clipboard from 'expo-clipboard';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';

const EXPO_PUBLIC_BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const STORAGE_KEY = 'pastebridge_session';
const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

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
}

export default function Index() {
  const [session, setSession] = useState<NotepadSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [lastCaptured, setLastCaptured] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [bubbleMode, setBubbleMode] = useState(false);
  
  // Animation for floating bubble
  const pan = useRef(new Animated.ValueXY({ x: SCREEN_WIDTH - 100, y: SCREEN_HEIGHT / 2 })).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;

  const webViewUrl = session
    ? `${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${session.code}/view`
    : '';

  // Pulse animation for the bubble
  useEffect(() => {
    if (bubbleMode) {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.1,
            duration: 1000,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 1000,
            useNativeDriver: true,
          }),
        ])
      );
      pulse.start();
      return () => pulse.stop();
    }
  }, [bubbleMode]);

  // Pan responder for draggable bubble
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        pan.setOffset({
          x: (pan.x as any)._value,
          y: (pan.y as any)._value,
        });
      },
      onPanResponderMove: Animated.event([null, { dx: pan.x, dy: pan.y }], {
        useNativeDriver: false,
      }),
      onPanResponderRelease: () => {
        pan.flattenOffset();
      },
    })
  ).current;

  useEffect(() => {
    loadOrCreateSession();
  }, []);

  const loadOrCreateSession = async () => {
    try {
      setLoading(true);
      setError('');

      const savedSession = await AsyncStorage.getItem(STORAGE_KEY);
      if (savedSession) {
        const parsed = JSON.parse(savedSession);
        const response = await fetch(
          `${EXPO_PUBLIC_BACKEND_URL}/api/notepad/${parsed.code}`
        );
        if (response.ok) {
          const data = await response.json();
          setSession(data);
          setLoading(false);
          return;
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

      if (!response.ok) throw new Error('Failed to send');

      const updatedNotepad = await response.json();
      setSession(updatedNotepad);
      setLastCaptured(clipboardText);
      setSuccessMessage('Sent!');
      Vibration.vibrate(50);

      setTimeout(() => setSuccessMessage(''), 2000);
    } catch (err) {
      console.error('Error capturing:', err);
      setError('Failed to send');
      Vibration.vibrate(100);
    } finally {
      setSending(false);
    }
  };

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
            setSession({ ...session, entries: [] });
            setLastCaptured('');
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
    Alert.alert('New Session', 'Create new notepad with new code?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Create New',
        onPress: async () => {
          setLoading(true);
          await AsyncStorage.removeItem(STORAGE_KEY);
          await createNewSession();
          setLastCaptured('');
          setLoading(false);
        },
      },
    ]);
  };

  // Floating Bubble Mode
  if (bubbleMode && session) {
    return (
      <View style={styles.bubbleContainer}>
        <StatusBar style="light" />
        
        {/* Exit bubble mode button */}
        <TouchableOpacity
          style={styles.exitBubbleBtn}
          onPress={() => setBubbleMode(false)}
        >
          <Ionicons name="expand-outline" size={24} color="#60a5fa" />
        </TouchableOpacity>

        {/* Code display */}
        <View style={styles.bubbleCodeContainer}>
          <Text style={styles.bubbleCodeLabel}>Your Code:</Text>
          <Text style={styles.bubbleCode}>{session.code}</Text>
          <Text style={styles.bubbleHint}>Type this on your PC</Text>
        </View>

        {/* Floating capture button */}
        <Animated.View
          style={[
            styles.floatingBubble,
            {
              transform: [
                { translateX: pan.x },
                { translateY: pan.y },
                { scale: pulseAnim },
              ],
            },
          ]}
          {...panResponder.panHandlers}
        >
          <TouchableOpacity
            style={[
              styles.bubbleButton,
              sending && styles.bubbleButtonSending,
            ]}
            onPress={captureAndSend}
            disabled={sending}
            activeOpacity={0.8}
          >
            {sending ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Ionicons name="clipboard" size={32} color="#fff" />
            )}
          </TouchableOpacity>
        </Animated.View>

        {/* Status message */}
        {(error || successMessage) && (
          <View style={styles.bubbleStatus}>
            <Text style={[styles.bubbleStatusText, error ? styles.errorText : styles.successText]}>
              {error || successMessage}
            </Text>
          </View>
        )}

        {/* Entry count */}
        <View style={styles.bubbleEntryCount}>
          <Text style={styles.entryCountText}>{session.entries.length} entries</Text>
        </View>
      </View>
    );
  }

  // Loading state
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

  // Main UI
  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>PasteBridge</Text>
        <TouchableOpacity
          style={styles.minimizeBtn}
          onPress={() => setBubbleMode(true)}
        >
          <Ionicons name="contract-outline" size={22} color="#60a5fa" />
        </TouchableOpacity>
      </View>

      {/* Code Display Card */}
      {session && (
        <View style={styles.codeCard}>
          <Text style={styles.codeLabel}>YOUR CODE</Text>
          <TouchableOpacity onPress={copyCode} activeOpacity={0.7}>
            <Text style={styles.codeText}>{session.code}</Text>
          </TouchableOpacity>
          <Text style={styles.codeHint}>Type this at the website on your PC</Text>
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

      {/* Bubble Mode Prompt */}
      <TouchableOpacity
        style={styles.bubbleModePrompt}
        onPress={() => setBubbleMode(true)}
      >
        <Ionicons name="apps" size={20} color="#60a5fa" />
        <Text style={styles.bubbleModeText}>Switch to Mini Mode</Text>
        <Ionicons name="chevron-forward" size={16} color="#60a5fa" />
      </TouchableOpacity>

      {/* Bottom Actions */}
      <View style={styles.bottomActions}>
        <TouchableOpacity style={styles.bottomBtn} onPress={clearNotepad}>
          <Ionicons name="trash-outline" size={20} color="#71717a" />
          <Text style={styles.bottomBtnText}>Clear</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.bottomBtn} onPress={startNewSession}>
          <Ionicons name="add-circle-outline" size={20} color="#71717a" />
          <Text style={styles.bottomBtnText}>New Code</Text>
        </TouchableOpacity>
      </View>

      {/* Instructions */}
      <View style={styles.instructions}>
        <Text style={styles.instructionsTitle}>How to use:</Text>
        <Text style={styles.instructionsText}>
          1. Go to the website on your PC{'\n'}
          2. Enter the code shown above{'\n'}
          3. Copy text on your phone{'\n'}
          4. Tap "Capture & Send"{'\n'}
          5. Text appears on your PC!
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
  minimizeBtn: {
    padding: 8,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    borderRadius: 8,
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
    marginTop: 32,
    backgroundColor: '#3b82f6',
    borderRadius: 24,
    paddingVertical: 36,
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
  bubbleModePrompt: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 24,
    marginHorizontal: 20,
    paddingVertical: 14,
    backgroundColor: 'rgba(96, 165, 250, 0.08)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(96, 165, 250, 0.2)',
  },
  bubbleModeText: {
    color: '#60a5fa',
    fontSize: 15,
    fontWeight: '500',
  },
  bottomActions: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 32,
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

  // Bubble Mode Styles
  bubbleContainer: {
    flex: 1,
    backgroundColor: '#0f0f1a',
  },
  exitBubbleBtn: {
    position: 'absolute',
    top: 60,
    right: 20,
    padding: 12,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    borderRadius: 12,
    zIndex: 100,
  },
  bubbleCodeContainer: {
    position: 'absolute',
    top: 120,
    left: 20,
    right: 20,
    alignItems: 'center',
  },
  bubbleCodeLabel: {
    fontSize: 14,
    color: '#71717a',
    marginBottom: 8,
  },
  bubbleCode: {
    fontSize: 48,
    fontWeight: '700',
    color: '#60a5fa',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    letterSpacing: 3,
  },
  bubbleHint: {
    fontSize: 14,
    color: '#52525b',
    marginTop: 8,
  },
  floatingBubble: {
    position: 'absolute',
    width: 80,
    height: 80,
  },
  bubbleButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#3b82f6',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#3b82f6',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.5,
    shadowRadius: 12,
    elevation: 10,
  },
  bubbleButtonSending: {
    backgroundColor: '#1e3a5f',
  },
  bubbleStatus: {
    position: 'absolute',
    bottom: 120,
    left: 0,
    right: 0,
    alignItems: 'center',
  },
  bubbleStatusText: {
    fontSize: 16,
    fontWeight: '600',
    paddingHorizontal: 20,
    paddingVertical: 10,
    backgroundColor: 'rgba(0,0,0,0.5)',
    borderRadius: 20,
    overflow: 'hidden',
  },
  bubbleEntryCount: {
    position: 'absolute',
    bottom: 60,
    left: 0,
    right: 0,
    alignItems: 'center',
  },
  entryCountText: {
    color: '#52525b',
    fontSize: 14,
  },
});

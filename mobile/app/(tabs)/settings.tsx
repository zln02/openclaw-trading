import { useEffect, useState } from 'react';
import { Pressable, SafeAreaView, Switch, Text, TextInput, View } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { usePushRegistration } from '../../hooks/usePushRegistration';

export default function SettingsScreen() {
  const [apiBase, setApiBase] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [notifications, setNotifications] = useState(true);
  const [status, setStatus] = useState('');
  const { busy, registerDevice } = usePushRegistration();

  useEffect(() => {
    Promise.all([
      SecureStore.getItemAsync('openclaw_api_base'),
      SecureStore.getItemAsync('openclaw_api_key'),
    ]).then(([base, key]) => {
      setApiBase(base || '');
      setApiKey(key || '');
    });
  }, []);

  const onSave = async () => {
    await SecureStore.setItemAsync('openclaw_api_base', apiBase.trim());
    await SecureStore.setItemAsync('openclaw_api_key', apiKey.trim());
    setStatus('Credentials saved');
  };

  const onRegisterPush = async () => {
    try {
      const token = await registerDevice();
      setNotifications(true);
      setStatus(`Push connected: ${token.slice(0, 18)}...`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Push registration failed');
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#f3efe4' }}>
      <View style={{ flex: 1, padding: 18, gap: 16 }}>
        <Text style={{ fontSize: 28, fontWeight: '800', color: '#112b1f' }}>Settings</Text>
        <TextInput value={apiBase} onChangeText={setApiBase} placeholder="API Base URL" style={{ borderWidth: 1, borderColor: '#c7bda9', borderRadius: 18, padding: 14, backgroundColor: '#fffaf0' }} />
        <TextInput value={apiKey} onChangeText={setApiKey} placeholder="Public API Key" style={{ borderWidth: 1, borderColor: '#c7bda9', borderRadius: 18, padding: 14, backgroundColor: '#fffaf0' }} />
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#fffaf0', borderRadius: 18, padding: 14 }}>
          <Text style={{ color: '#1a2d24', fontWeight: '600' }}>Push Notifications</Text>
          <Switch value={notifications} onValueChange={setNotifications} />
        </View>
        <Pressable onPress={onSave} style={{ backgroundColor: '#112b1f', borderRadius: 18, padding: 16 }}>
          <Text style={{ color: '#f3efe4', fontWeight: '700', textAlign: 'center' }}>Save</Text>
        </Pressable>
        <Pressable onPress={onRegisterPush} style={{ backgroundColor: '#1f4d7a', borderRadius: 18, padding: 16, opacity: busy ? 0.6 : 1 }}>
          <Text style={{ color: '#f3efe4', fontWeight: '700', textAlign: 'center' }}>
            {busy ? 'Registering...' : 'Register Push'}
          </Text>
        </Pressable>
        <Text style={{ color: '#4d5c51' }}>{status || 'Push not registered yet'}</Text>
      </View>
    </SafeAreaView>
  );
}

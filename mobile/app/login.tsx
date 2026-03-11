import { useState } from 'react';
import { router } from 'expo-router';
import { Pressable, SafeAreaView, Text, TextInput, View } from 'react-native';
import * as SecureStore from 'expo-secure-store';

export default function LoginScreen() {
  const [apiBase, setApiBase] = useState('http://localhost:8080');
  const [apiKey, setApiKey] = useState('');

  const onSave = async () => {
    await SecureStore.setItemAsync('openclaw_api_base', apiBase.trim());
    await SecureStore.setItemAsync('openclaw_api_key', apiKey.trim());
    router.replace('/(tabs)/btc');
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#f3efe4' }}>
      <View style={{ flex: 1, padding: 24, justifyContent: 'center', gap: 16 }}>
        <Text style={{ fontSize: 34, fontWeight: '800', color: '#112b1f' }}>OpenClaw</Text>
        <Text style={{ fontSize: 15, color: '#4d5c51' }}>Public API 키로 모바일 대시보드에 로그인</Text>
        <TextInput
          value={apiBase}
          onChangeText={setApiBase}
          placeholder="API Base URL"
          autoCapitalize="none"
          style={{ borderWidth: 1, borderColor: '#c7bda9', borderRadius: 18, padding: 14, backgroundColor: '#fffaf0' }}
        />
        <TextInput
          value={apiKey}
          onChangeText={setApiKey}
          placeholder="Public API Key"
          autoCapitalize="none"
          style={{ borderWidth: 1, borderColor: '#c7bda9', borderRadius: 18, padding: 14, backgroundColor: '#fffaf0' }}
        />
        <Pressable onPress={onSave} style={{ backgroundColor: '#112b1f', borderRadius: 18, padding: 16 }}>
          <Text style={{ color: '#f3efe4', fontWeight: '700', textAlign: 'center' }}>Connect</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

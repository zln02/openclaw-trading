import { Tabs } from 'expo-router';

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: '#112b1f', tabBarInactiveTintColor: '#7b8078' }}>
      <Tabs.Screen name="btc" options={{ title: 'BTC' }} />
      <Tabs.Screen name="kr" options={{ title: 'KR' }} />
      <Tabs.Screen name="us" options={{ title: 'US' }} />
      <Tabs.Screen name="settings" options={{ title: 'Settings' }} />
    </Tabs>
  );
}

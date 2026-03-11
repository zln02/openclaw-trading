import { useEffect, useState } from 'react';
import { Redirect } from 'expo-router';
import * as SecureStore from 'expo-secure-store';

export default function IndexScreen() {
  const [target, setTarget] = useState<'/login' | '/(tabs)/btc' | null>(null);

  useEffect(() => {
    let active = true;

    (async () => {
      const [base, key] = await Promise.all([
        SecureStore.getItemAsync('openclaw_api_base'),
        SecureStore.getItemAsync('openclaw_api_key'),
      ]);
      if (!active) {
        return;
      }
      setTarget(base && key ? '/(tabs)/btc' : '/login');
    })();

    return () => {
      active = false;
    };
  }, []);

  if (!target) {
    return null;
  }

  return <Redirect href={target} />;
}

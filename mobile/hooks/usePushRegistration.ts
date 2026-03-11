import { useState } from 'react';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';

import { getConfig } from './useSignals';

export function usePushRegistration() {
  const [busy, setBusy] = useState(false);

  const registerDevice = async () => {
    setBusy(true);
    try {
      const permission = await Notifications.requestPermissionsAsync();
      if (permission.status !== 'granted') {
        throw new Error('Notification permission denied');
      }

      const projectId =
        Constants.expoConfig?.extra?.eas?.projectId ||
        Constants.easConfig?.projectId;

      const tokenResult = await Notifications.getExpoPushTokenAsync(
        projectId ? { projectId } : undefined,
      );

      const { base, key } = await getConfig();
      const response = await fetch(`${base}/api/v1/push/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': key,
        },
        body: JSON.stringify({
          token: tokenResult.data,
          platform: 'expo',
          label: 'mobile-app',
          enabled: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return tokenResult.data;
    } finally {
      setBusy(false);
    }
  };

  return { busy, registerDevice };
}

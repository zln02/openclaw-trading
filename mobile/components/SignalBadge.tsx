import { Text, View } from 'react-native';

const palette = {
  good: { bg: '#dcefe3', fg: '#0f6a55' },
  bad: { bg: '#f4d8cf', fg: '#8e2f1f' },
  neutral: { bg: '#e9e1d3', fg: '#635a4d' },
};

export function SignalBadge({ label, tone = 'neutral' }: { label: string; tone?: 'good' | 'bad' | 'neutral' }) {
  const style = palette[tone];
  return (
    <View style={{ backgroundColor: style.bg, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 8 }}>
      <Text style={{ color: style.fg, fontWeight: '700', fontSize: 12 }}>{label}</Text>
    </View>
  );
}

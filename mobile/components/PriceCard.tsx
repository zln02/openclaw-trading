import { Text, View } from 'react-native';

export function PriceCard({ title, value, subtitle, accent }: { title: string; value: string; subtitle: string; accent: string }) {
  return (
    <View style={{ backgroundColor: '#fffaf0', borderRadius: 26, padding: 20, borderWidth: 1, borderColor: '#e6dbc8' }}>
      <Text style={{ color: '#6a756d', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>{title}</Text>
      <Text style={{ color: accent, fontSize: 34, fontWeight: '800', marginTop: 8 }}>{value}</Text>
      <Text style={{ color: '#4d5c51', marginTop: 8 }}>{subtitle}</Text>
    </View>
  );
}

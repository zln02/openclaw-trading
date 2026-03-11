import { Text, View } from 'react-native';

type Props = {
  btc: number;
  kr: number;
  us: number;
  cash: number;
};

const segments = [
  { key: 'btc', label: 'BTC', color: '#112b1f' },
  { key: 'kr', label: 'KR', color: '#1f4d7a' },
  { key: 'us', label: 'US', color: '#0f6a55' },
  { key: 'cash', label: 'CASH', color: '#8f7f5e' },
] as const;

export function AllocationStrip({ btc, kr, us, cash }: Props) {
  const values = { btc, kr, us, cash };

  return (
    <View style={{ backgroundColor: '#fffaf0', borderRadius: 22, padding: 18, gap: 12 }}>
      <Text style={{ fontSize: 18, fontWeight: '700', color: '#112b1f' }}>Portfolio Allocation</Text>
      <View style={{ flexDirection: 'row', width: '100%', height: 14, borderRadius: 999, overflow: 'hidden', backgroundColor: '#ece3d4' }}>
        {segments.map((segment) => (
          <View
            key={segment.key}
            style={{
              width: `${Math.max(0, Math.min(100, values[segment.key]))}%`,
              backgroundColor: segment.color,
            }}
          />
        ))}
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        {segments.map((segment) => (
          <Text key={segment.key} style={{ color: '#4d5c51' }}>
            {segment.label} {values[segment.key].toFixed(1)}%
          </Text>
        ))}
      </View>
    </View>
  );
}

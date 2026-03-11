import { View } from 'react-native';

export function MiniChart({ values, color }: { values: number[]; color: string }) {
  const max = Math.max(...values, 1);
  return (
    <View style={{ backgroundColor: '#fffaf0', borderRadius: 22, padding: 18, height: 120, flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
      {values.map((value, idx) => (
        <View
          key={`${idx}-${value}`}
          style={{
            flex: 1,
            height: `${Math.max(12, (value / max) * 100)}%`,
            backgroundColor: color,
            borderRadius: 999,
            opacity: idx === values.length - 1 ? 1 : 0.55,
          }}
        />
      ))}
    </View>
  );
}

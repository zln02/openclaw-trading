import { Text, View } from 'react-native';

export function TradeList({ title, items }: { title: string; items: string[] }) {
  return (
    <View style={{ backgroundColor: '#fffaf0', borderRadius: 22, padding: 18, gap: 10 }}>
      <Text style={{ fontSize: 18, fontWeight: '700', color: '#112b1f' }}>{title}</Text>
      {(items.length ? items : ['No data']).map((item) => (
        <Text key={item} style={{ color: '#4d5c51' }}>{item}</Text>
      ))}
    </View>
  );
}

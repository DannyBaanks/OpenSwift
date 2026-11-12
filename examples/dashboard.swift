import SwiftUI

struct Dashboard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Resumen")
                .font(.largeTitle)
                .fontWeight(.bold)
            Text("Tu semana en OpenSwift")
                .font(.subheadline)
                .foregroundColor(.secondary)
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Builds")
                        .font(.caption)
                        .foregroundColor(.white)
                        .opacity(0.8)
                    Text("14")
                        .font(.system(size: 32, weight: .bold))
                        .foregroundColor(.white)
                }
                .padding(16)
                .frame(maxWidth: .infinity)
                .background(LinearGradient(colors: [.blue, .purple], startPoint: .topLeading, endPoint: .bottomTrailing))
                .cornerRadius(20)
                VStack(alignment: .leading, spacing: 6) {
                    Text("Previews")
                        .font(.caption)
                        .foregroundColor(.white)
                        .opacity(0.8)
                    Text("32")
                        .font(.system(size: 32, weight: .bold))
                        .foregroundColor(.white)
                }
                .padding(16)
                .frame(maxWidth: .infinity)
                .background(LinearGradient(colors: [.orange, .pink], startPoint: .topLeading, endPoint: .bottomTrailing))
                .cornerRadius(20)
            }
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Sincronizar en vivo", isOn: $live)
                Divider()
                Label("Sesión activa", systemImage: "bolt.fill")
            }
            .padding(16)
            .background(Color.gray.opacity(0.18))
            .cornerRadius(20)
            Spacer()
            Button("Nueva sesión") { }
                .buttonStyle(.borderedProminent)
                .frame(maxWidth: .infinity)
                .frame(height: 50)
                .cornerRadius(14)
        }
        .padding(20)
    }
}

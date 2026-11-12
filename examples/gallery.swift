import SwiftUI

struct Tile: View {
    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: "star.fill")
                .foregroundColor(.yellow)
            Text("Favorito")
                .font(.caption)
        }
        .padding(14)
        .frame(maxWidth: .infinity)
        .background(Color.gray.opacity(0.18))
        .cornerRadius(16)
    }
}

struct Gallery: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Galería")
                .font(.largeTitle)
                .fontWeight(.bold)
            HStack(spacing: 12) {
                ForEach(0..<3) { _ in
                    Tile()
                }
            }
            Label("Notificaciones", systemImage: "bell.fill")
            Label("Ajustes", systemImage: "gearshape")
            Label("Buscar", systemImage: "magnifyingglass")
            Spacer()
        }
        .padding(20)
    }
}

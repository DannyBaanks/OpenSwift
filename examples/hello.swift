import SwiftUI

struct Hello: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("opencode")
                .font(.system(size: 30, weight: .semibold))
                .foregroundColor(.white)
            Text("native / ios")
                .font(.system(size: 13))
                .foregroundColor(.white)
            Spacer()
            Button("connect") { }
                .frame(maxWidth: .infinity)
                .frame(height: 44)
        }
        .padding(18)
        .background(Color.black)
    }
}

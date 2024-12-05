import random
import sys
import sqlite3
from PyQt6.QtCore import Qt, QBasicTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QMainWindow, QFrame, QApplication, QLabel, QVBoxLayout, QWidget, QMessageBox


class Database:
    def __init__(self):
        self.connection = sqlite3.connect('tetris_scores.db')  # Устанавливаем соединение с базой данных
        self.create_table()  # Создаем таблицу для хранения очков

    def create_table(self):
        """Создает таблицу очков, если она еще не существует."""
        with self.connection:
            self.connection.execute('''
                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY,
                    score INTEGER NOT NULL
                )
            ''')

    def insert_score(self, score):
        """Вставляет новый счет в базу данных."""
        with self.connection:
            self.connection.execute('INSERT INTO scores (score) VALUES (?)', (score,))

    def get_max_score(self):
        """Извлекает максимальный счет из базы данных."""
        cursor = self.connection.cursor()
        cursor.execute('SELECT MAX(score) FROM scores')
        result = cursor.fetchone()
        return result[0] if result[0] is not None else 0

    def close(self):
        """Закрывает соединение с базой данных."""
        self.connection.close()


class Tetris(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()  # Инициализируем базу данных
        self.max_score = self.db.get_max_score()  # Получаем максимальный счет из базы данных
        self.initUI()  # Инициализируем пользовательский интерфейс

    def initUI(self):
        # Создаем центральный виджет и макет
        central_widget = QWidget()
        main_layout = QVBoxLayout()

        # Создаем игровую доску
        self.tboard = Board(self)  # Передаем экземпляр Tetris в Board

        # Создаем метку с инструкциями
        instructions_label = QLabel(
            "Управление:\n"
            "← → : Двигать влево/вправо\n"
            "↑ : Повернуть влево\n"
            "↓ : Повернуть вправо\n"
            "Пробел : Уронить фигуру\n"
            "P : Пауза/Продолжить\n"
            "D : Двигать вниз на одну линию\n"
            "R : Перезапустить игру"  # Добавлено управление для перезапуска игры
        )
        instructions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions_label.setFont(QFont('Arial', 10))
        instructions_label.setStyleSheet("""  # Устанавливаем стиль для метки с инструкциями
            background-color: #f0f0f0;
            border: 1px solid #999;
            border-radius: 5px;
            padding: 10px;
        """)

        # Добавляем доску и инструкции в макет
        main_layout.addWidget(self.tboard)
        main_layout.addWidget(instructions_label)

        # Устанавливаем макет для центрального виджета
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.statusbar = self.statusBar()
        self.tboard.msg2Statusbar[str].connect(self.statusbar.showMessage)  # Подключаем сигнал к статусной строке

        self.tboard.start()  # Запускаем игру

        self.resize(200, 500)  # Устанавливаем размер окна
        self.center()  # Центрируем окно
        self.setWindowTitle('Тетрис')  # Устанавливаем заголовок окна
        self.show()  # Показываем окно

    def closeEvent(self, event):
        """Обрабатывает событие закрытия окна, чтобы правильно закрыть базу данных."""
        self.db.close()  # Закрываем соединение с базой данных
        event.accept()  # Принимаем событие закрытия

    def center(self):
        """Центрирует окно на экране."""
        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())  # Перемещаем окно в верхний левый угол


class Board(QFrame):
    msg2Statusbar = pyqtSignal(str)  # Сигнал для передачи сообщений в строку состояния

    BoardWidth = 10  # Ширина доски
    BoardHeight = 22  # Высота доски
    Speed = 300  # Скорость игры

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_tetris = parent  # Сохраняем ссылку на экземпляр Tetris
        self.initBoard()  # Инициализируем игровую доску

    def initBoard(self):
        """Инициализирует игровую доску."""
        self.timer = QBasicTimer()  # Инициализируем таймер
        self.isWaitingAfterLine = False  # Флаг ожидания после удаления линии
        self.curX = 0  # Текущая позиция X
        self.curY = 0  # Текущая позиция Y
        self.numLinesRemoved = 0  # Количество удаленных линий
        self.board = []  # Игровая доска
        self.current_score = 0  # Инициализация текущих очков

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Устанавливаем фокус на доске
        self.isStarted = False  # Игра не начата
        self.isPaused = False  # Игра не на паузе
        self.clearBoard()  # Очищаем доску

    def shapeAt(self, x, y):
        """Определяет форму на позиции доски."""
        return self.board[(y * Board.BoardWidth) + x]

    def setShapeAt(self, x, y, shape):
        """Устанавливает форму на доске."""
        self.board[(y * Board.BoardWidth) + x] = shape

    def squareWidth(self):
        """Возвращает ширину одного квадрата."""
        return self.contentsRect().width() // Board.BoardWidth

    def squareHeight(self):
        """Возвращает высоту одного квадрата."""
        return self.contentsRect().height() // Board.BoardHeight

    def start(self):
        """Начинает игру."""
        if self.isPaused:
            return  # Если игра на паузе, возвращаемся

        self.isStarted = True  # Игра начата
        self.isWaitingAfterLine = False
        self.numLinesRemoved = 0  # Сбрасываем счетчик удаленных линий
        self.current_score = 0  # Сбрасываем текущие очки

        self.clearBoard()  # Очищаем доску

        # Передаем текущее и максимальное количество очков в строку состояния
        self.msg2Statusbar.emit(f"Очки: {self.current_score} | Макс Очки: {self.parent_tetris.max_score}")

        self.newPiece()  # Генерируем новую фигуру
        self.timer.start(Board.Speed, self)  # Запускаем таймер

    def pause(self):
        """Ставит игру на паузу."""
        if not self.isStarted:  # Если игра не начата, возвращаемся
            return

        self.isPaused = not self.isPaused  # Переключаем состояние паузы

        if self.isPaused:
            self.timer.stop()  # Останавливаем таймер
            self.msg2Statusbar.emit("Игра на паузе")  # Отправляем сообщение о паузе
        else:
            self.timer.start(Board.Speed, self)  # Возобновляем таймер
            self.msg2Statusbar.emit(f"Очки: {self.current_score} | Макс Очки: {self.parent_tetris.max_score}")

        self.update()  # Обновляем виджет

    def paintEvent(self, event):
        """Рисует все формы игры."""
        painter = QPainter(self)
        rect = self.contentsRect()

        boardTop = rect.bottom() - Board.BoardHeight * self.squareHeight()  # Определяем верхнюю границу доски

        for i in range(Board.BoardHeight):
            for j in range(Board.BoardWidth):
                shape = self.shapeAt(j, Board.BoardHeight - i - 1)  # Получаем форму для рисования

                if shape != Tetrominoe.NoShape:  # Если форма не пустая
                    self.drawSquare(painter,
                                    rect.left() + j * self.squareWidth(),
                                    boardTop + i * self.squareHeight(), shape)  # Рисуем квадрат

        if self.curPiece.shape() != Tetrominoe.NoShape:  # Если текущая фигура не пустая
            for i in range(4):
                x = self.curX + self.curPiece.x(i)
                y = self.curY - self.curPiece.y(i)
                self.drawSquare(painter, rect.left() + x * self.squareWidth(),
                                boardTop + (Board.BoardHeight - y - 1) * self.squareHeight(),
                                self.curPiece.shape())

    def keyPressEvent(self, event):
        """Обрабатывает события нажатия клавиш."""
        if not self.isStarted or self.curPiece.shape() == Tetrominoe.NoShape:  # Если игра не начата или фигура пустая
            super(Board, self).keyPressEvent(event)  # Обрабатываем событие нажатия клавиши
            return

        key = event.key()  # Получаем нажатую клавишу

        if key == Qt.Key.Key_P:  # Если нажата клавиша "P", ставим игру на паузу
            self.pause()
            return

        if self.isPaused:  # Если игра на паузе, возвращаемся
            return

        elif key == Qt.Key.Key_Left.value:  # Если нажата клавиша влево
            self.tryMove(self.curPiece, self.curX - 1, self.curY)  # Двигаем фигуру влево

        elif key == Qt.Key.Key_Right.value:  # Если нажата клавиша вправо
            self.tryMove(self.curPiece, self.curX + 1, self.curY)  # Двигаем фигуру вправо

        elif key == Qt.Key.Key_Down.value:  # Если нажата клавиша вниз
            self.tryMove(self.curPiece.rotateRight(), self.curX, self.curY)  # Поворачиваем фигуру вправо

        elif key == Qt.Key.Key_Up.value:  # Если нажата клавиша вверх
            self.tryMove(self.curPiece.rotateLeft(), self.curX, self.curY)  # Поворачиваем фигуру влево

        elif key == Qt.Key.Key_Space.value:  # Если нажата клавиша пробела
            self.dropDown()  # Уронить фигуру

        elif key == Qt.Key.Key_D.value:  # Если нажата клавиша "D"
            self.oneLineDown()  # Двигаем фигуру вниз на одну линию

        elif key == Qt.Key.Key_R.value:  # Если нажата клавиша "R"
            self.restartGame()  # Перезапускаем игру

        else:
            super(Board, self).keyPressEvent(event)  # Обрабатываем остальные клавиши

    def timerEvent(self, event):
        """Обрабатывает событие таймера."""
        if event.timerId() == self.timer.timerId():  # Если это наш таймер
            if self.isWaitingAfterLine:  # Если ждем после удаления линии
                self.isWaitingAfterLine = False
                self.newPiece()  # Генерируем новую фигуру
            else:
                self.oneLineDown()  # Двигаем фигуру вниз
        else:
            super(Board, self).timerEvent(event)  # Обрабатываем остальные события таймера

    def clearBoard(self):
        """Очищает формы с доски."""
        self.board = [Tetrominoe.NoShape] * (Board.BoardHeight * Board.BoardWidth)  # Очищаем доску

    def dropDown(self):
        """Уроняет фигуру вниз."""
        newY = self.curY

        while newY > 0:  # Двигаем фигуру вниз, пока это возможно
            if not self.tryMove(self.curPiece, self.curX, newY - 1):  # Если не можем двигаться
                break
            newY -= 1

        self.pieceDropped()  # Фигура упала

    def oneLineDown(self):
        """Двигает фигуру вниз на одну линию."""
        if not self.tryMove(self.curPiece, self.curX, self.curY - 1):  # Если не можем двигаться вниз
            self.pieceDropped()  # Фигура упала

    def pieceDropped(self):
        """После падения фигуры, удаляет полные линии и создает новую фигуру."""
        for i in range(4):
            x = self.curX + self.curPiece.x(i)
            y = self.curY - self.curPiece.y(i)
            self.setShapeAt(x, y, self.curPiece.shape())  # Устанавливаем фигуру на доску

        self.removeFullLines()  # Проверяем и удаляем полные линии

        if not self.isWaitingAfterLine:  # Если не ждем после удаления линии
            self.newPiece()  # Генерируем новую фигуру

    def removeFullLines(self):
        """Удаляет все полные линии с доски."""
        numFullLines = 0
        rowsToRemove = []  # Список полных линий

        for i in range(Board.BoardHeight):
            n = 0
            for j in range(Board.BoardWidth):
                if not self.shapeAt(j, i) == Tetrominoe.NoShape:  # Если ячейка не пустая
                    n += 1

            if n == 10:  # Если линия полная
                rowsToRemove.append(i)  # Добавляем в список полных линий

        rowsToRemove.reverse()  # Переворачиваем список для удаления

        for m in rowsToRemove:
            for k in range(m, Board.BoardHeight):
                for l in range(Board.BoardWidth):
                    self.setShapeAt(l, k, self.shapeAt(l, k + 1))  # Сдвигаем линии вниз

        numFullLines = len(rowsToRemove)  # Считаем количество полных линий

        if numFullLines > 0:  # Если есть полные линии
            self.numLinesRemoved += numFullLines
            self.current_score += numFullLines * 100  # Добавляем очки за полные линии
            self.msg2Statusbar.emit(f"Очки: {self.current_score} | Макс Очки: {self.parent_tetris.max_score}")

            # Обновляем максимальные очки, если текущие больше
            if self.current_score > self.parent_tetris.max_score:
                self.parent_tetris.max_score = self.current_score

            # Вставляем текущие очки в базу данных
            self.parent_tetris.db.insert_score(self.current_score)

        self.isWaitingAfterLine = True  # Устанавливаем флаг ожидания
        self.curPiece.setShape(Tetrominoe.NoShape)  # Убираем текущую фигуру
        self.update()  # Обновляем виджет

    def newPiece(self):
        """Создает новую фигуру."""
        self.curPiece = Shape()  # Создаем новую фигуру
        self.curPiece.setRandomShape()  # Устанавливаем случайную фигуру
        self.curX = Board.BoardWidth // 2 + 1  # Устанавливаем позицию X
        self.curY = Board.BoardHeight - 1 + self.curPiece.minY()  # Устанавливаем позицию Y

        if not self.tryMove(self.curPiece, self.curX, self.curY):  # Если не можем установить фигуру
            self.curPiece.setShape(Tetrominoe.NoShape)  # Убираем фигуру
            self.timer.stop()  # Останавливаем таймер
            self.isStarted = False  # Игра закончена
            self.msg2Statusbar.emit("Игра окончена")  # Отправляем сообщение о конце игры

            # Запрашиваем перезапуск игры
            self.restartGame()

    def restartGame(self):
        """Запрашивает у пользователя перезапуск игры."""
        reply = QMessageBox.question(self, 'Игра окончена',
                                     "Хотите перезапустить игру?",  # Запрос на перезапуск
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.Yes)

        if reply == QMessageBox.StandardButton.Yes:
            self.start()  # Перезапускаем игру
        else:
            QApplication.quit()  # Выходим из приложения

    def tryMove(self, newPiece, newX, newY):
        """Пытается переместить фигуру."""
        for i in range(4):
            x = newX + newPiece.x(i)
            y = newY - newPiece.y(i)

            if x < 0 or x >= Board.BoardWidth or y < 0 or y >= Board.BoardHeight:  # Проверяем границы
                return False

            if self.shapeAt(x, y) != Tetrominoe.NoShape:  # Проверяем на занятые ячейки
                return False

        self.curPiece = newPiece  # Устанавливаем новую фигуру
        self.curX = newX  # Обновляем позицию X
        self.curY = newY  # Обновляем позицию Y
        self.update()  # Обновляем виджет

        return True  # Успешное движение

    def drawSquare(self, painter, x, y, shape):
        """Рисует квадрат фигуры."""
        colorTable = [0x000000, 0xCC6666, 0x66CC66, 0x6666CC,
                      0xCCCC66, 0xCC66CC, 0x66CCCC, 0xDAAA00]

        color = QColor(colorTable[shape])  # Получаем цвет фигуры
        painter.fillRect(x + 1, y + 1, self.squareWidth() - 2,
                         self.squareHeight() - 2, color)  # Рисуем квадрат

        painter.setPen(color.lighter())  # Устанавливаем цвет для линий
        painter.drawLine(x, y + self.squareHeight() - 1, x, y)  # Рисуем линии

        painter.setPen(color.darker())  # Устанавливаем цвет для темных линий
        painter.drawLine(x + 1, y + self.squareHeight() - 1,
                         x + self.squareWidth() - 1, y + self.squareHeight() - 1)
        painter.drawLine(x + self.squareWidth() - 1,
                         y + self.squareHeight() - 1, x + self.squareWidth() - 1, y + 1)


class Tetrominoe:
    NoShape = 0
    ZShape = 1
    SShape = 2
    LineShape = 3
    TShape = 4
    SquareShape = 5
    LShape = 6
    MirroredLShape = 7


class Shape:
    coordsTable = (
        ((0, 0), (0, 0), (0, 0), (0, 0)),
        ((0, -1), (0, 0), (-1, 0), (-1, 1)),
        ((0, -1), (0, 0), (1, 0), (1, 1)),
        ((0, -1), (0, 0), (0, 1), (0, 2)),
        ((-1, 0), (0, 0), (1, 0), (0, 1)),
        ((0, 0), (1, 0), (0, 1), (1, 1)),
        ((-1, -1), (0, -1), (0, 0), (0, 1)),
        ((1, -1), (0, -1), (0, 0), (0, 1))
    )

    def __init__(self):
        self.coords = [[0, 0] for _ in range(4)]  # Координаты фигуры
        self.pieceShape = Tetrominoe.NoShape  # Форма фигуры
        self.setShape(Tetrominoe.NoShape)  # Устанавливаем форму

    def shape(self):
        """Возвращает форму."""
        return self.pieceShape

    def setShape(self, shape):
        """Устанавливает форму."""
        table = Shape.coordsTable[shape]  # Получаем таблицу координат для фигуры

        for i in range(4):
            for j in range(2):
                self.coords[i][j] = table[i][j]  # Устанавливаем координаты

        self.pieceShape = shape  # Устанавливаем форму

    def setRandomShape(self):
        """Выбирает случайную форму."""
        self.setShape(random.randint(1, 7))

    def x(self, index):
        """Возвращает координату x."""
        return self.coords[index][0]

    def y(self, index):
        """Возвращает координату y."""
        return self.coords[index][1]

    def setX(self, index, x):
        """Устанавливает координату x."""
        self.coords[index][0] = x

    def setY(self, index, y):
        """Устанавливает координату y."""
        self.coords[index][1] = y

    def minX(self):
        """Возвращает минимальное значение x."""
        m = self.coords[0][0]
        for i in range(4):
            m = min(m, self.coords[i][0])  # Находим минимальную координату x
        return m

    def maxX(self):
        """Возвращает максимальное значение x."""
        m = self.coords[0][0]
        for i in range(4):
            m = max(m, self.coords[i][0])  # Находим максимальную координату x
        return m

    def minY(self):
        """Возвращает минимальное значение y."""
        m = self.coords[0][1]
        for i in range(4):
            m = min(m, self.coords[i][1])  # Находим минимальную координату y
        return m

    def maxY(self):
        """Возвращает максимальное значение y."""
        m = self.coords[0][1]
        for i in range(4):
            m = max(m, self.coords[i][1])  # Находим максимальную координату y
        return m

    def rotateLeft(self):
        """Поворачивает фигуру влево."""
        if self.pieceShape == Tetrominoe.SquareShape:
            return self  # Если фигура квадрат, не поворачиваем

        result = Shape()  # Создаем новую фигуру
        result.pieceShape = self.pieceShape  # Устанавливаем форму

        for i in range(4):
            result.setX(i, self.y(i))  # Поворачиваем фигуру влево
            result.setY(i, -self.x(i))

        return result

    def rotateRight(self):
        """Поворачивает фигуру вправо."""
        if self.pieceShape == Tetrominoe.SquareShape:
            return self  # Если фигура квадрат, не поворачиваем

        result = Shape()  # Создаем новую фигуру
        result.pieceShape = self.pieceShape  # Устанавливаем форму

        for i in range(4):
            result.setX(i, -self.y(i))  # Поворачиваем фигуру вправо
            result.setY(i, self.x(i))

        return result


def main():
    app = QApplication([])  # Создаем приложение

    tetris = Tetris()  # Создаем экземпляр Tetris
    sys.exit(app.exec())  # Запускаем приложение


if __name__ == '__main__':
    main()  # Запускаем основную функцию
import rc

class Styles:
    main_window = """
        background-color: rgb(23, 23, 23);
    """

    line_edit = """
        QLineEdit {
            border: 2px solid rgb(45, 45, 45);
            border-radius: 5px;
            padding: 15px;
            background-color: rgb(30, 30, 30);
            color: rgb(163, 168, 163);
        }
        QLineEdit:hover {
            border: 2px solid rgb(89, 222, 93);
        }
        QLineEdit:focus {
            color: rgb(255, 255, 255);
            selection-background-color: rgb(255, 121, 198);
        }
    """
    
    line_edit_ok = """
    QLineEdit {
        border: 2px solid rgb(0, 255, 123);  /* Borda verde de sucesso */
        border-radius: 5px;
        padding: 15px;
        background-color: rgb(30, 30, 30);
        color: rgb(25, 255, 255);
    }
    QLineEdit:hover {
        border: 2px solid rgb(0, 200, 100);
    }
    QLineEdit:focus {
        color: rgb(255, 255, 255);
        selection-background-color: rgb(0, 255, 123);
    }
"""

    
    line_edit_error = """
    QLineEdit {
        border: 2px solid rgb(255, 37, 37); /* Borda vermelha */
        border-radius: 5px;
        padding: 15px;
        background-color: rgb(30, 30, 30);
        color: rgb(25, 255, 255);
    }
    QLineEdit:hover {
        border: 2px solid rgb(255, 0, 0);
    }
    QLineEdit:focus {
        color: rgb(255, 255, 255);
        selection-background-color: rgb(255, 121, 198);
    }
"""

    button = """
        QPushButton {
            background-color: rgb(50, 50, 50);
            border: 2px solid rgb(60, 60, 60);
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: rgb(60, 60, 60);
            border: 2px solid rgb(70, 70, 70);
        }
        QPushButton:pressed {
            border: 2px solid rgb(255, 255, 255);
            color: rgb(35, 35, 35);
        }
    """

    popup_error = """
        background-color: rgb(255, 37, 37);
        border-radius: 5px;
        border: none;
    """

    popup_ok = """
        background-color: rgb(0, 255, 123);
        border-radius: 5px;
        border: none;
    """
    close_button = """
        QPushButton {
            border-radius: 5px;
            background-image: url(:/imgs/x.png);
            background-position: center;
            background-color: rgb(60, 60, 60);
        }
        QPushButton:hover {
            background-color: rgb(50, 50, 50);
            color: rgb(200, 200, 200);
        }
        QPushButton:pressed {
            background-color: rgb(35, 35, 35);
            color: rgb(200, 200, 200);
            border: none;
        }
    """
    loading_screen = """
        QWidget {
            background-color: transparent;
        }
        
        QLabel#loading_text {
            color: white;
            font-size: 16px;
            font-weight: bold;
        }
    """